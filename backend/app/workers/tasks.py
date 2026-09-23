"""
Celery tasks for the seek-aware, priority-driven processing pipeline.

Flow:
  prepare_video      -- runs once per video: get local file, transcribe audio
                         (cached), split into chunks, create Chunk rows,
                         kick off schedule_chunks.
  schedule_chunks     -- self-rescheduling dispatcher. Looks at the `chunks`
                         table (the real priority queue), dispatches up to
                         MAX_CONCURRENT_CHUNKS pending chunks (lowest
                         priority first), and gets re-triggered by every
                         chunk task when it finishes and by the /seek
                         endpoint when the user jumps around.
  process_chunk_task -- does the actual visual + audio censorship for ONE
                         chunk, uploads its HLS segments, marks it COMPLETED.
                         Never re-runs on a chunk that's already COMPLETED.
"""
import os
import sys
import uuid
import tempfile

from sqlalchemy import func

from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.video import Video, VideoStatus
from app.models.job import JobStatus
from app.models.chunk import Chunk, ChunkStatus
from app.services import storage, transcript_cache
from app.services.jobs import update_job_progress
from app.services.youtube import download_youtube_video

# Make the sibling `processor/` package importable from the worker container.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "processor"))
from video.chunker import chunk_video  # noqa: E402
from pipeline.chunk_pipeline import process_chunk  # noqa: E402
from pipeline.audio_pipeline import detect_profanity_for_video  # noqa: E402
from audio.censor import beep_censor_audio  # noqa: E402
from audio.transcriber import WordTiming  # noqa: E402
from utils.ffmpeg import probe_duration, to_hls, extract_audio  # noqa: E402


@celery_app.task(name="prepare_video")
def prepare_video(job_id: str, video_id: str):
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == uuid.UUID(video_id)).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        update_job_progress(db, uuid.UUID(job_id), progress=1.0, status=JobStatus.RUNNING)
        video.status = VideoStatus.PROCESSING
        db.commit()

        work_dir = tempfile.mkdtemp(prefix=f"prep_{video_id}_")

        # Step 1: get a local copy of the source video.
        if video.source_type.value == "youtube":
            local_path = download_youtube_video(video.source_url)
            storage.upload_file(local_path, storage.object_path(video.id, "original.mp4"))
        else:
            local_path = os.path.join(work_dir, "original.mp4")
            storage.download_file(video.storage_path, local_path)

        video.duration = probe_duration(local_path)
        db.commit()

        # Step 2: transcribe + AI-flag profanity ONCE across the whole video,
        # cache the result — every chunk task below just filters this by its
        # own time window rather than re-running Whisper/Claude per chunk.
        flagged_words = detect_profanity_for_video(local_path, work_dir)
        transcript_cache.save_flagged_words(video_id, [
            {"index": w.index, "word": w.word, "start": w.start, "end": w.end}
            for w in flagged_words
        ])

        # Step 3: split into chunks, probe each chunk's REAL duration (ffmpeg's
        # segment muxer cuts on keyframes, so lengths aren't exactly uniform),
        # upload each raw chunk, and create its Chunk row. priority defaults
        # to `index`, i.e. sequential-from-the-start until a seek reorders it.
        chunk_paths = chunk_video(local_path, work_dir, chunk_seconds=settings.CHUNK_SECONDS)
        start = 0.0
        for idx, path in enumerate(chunk_paths):
            duration = probe_duration(path)
            raw_key = storage.object_path(video_id, "raw_chunks", f"chunk_{idx:04d}.mp4")
            storage.upload_file(path, raw_key)

            db.add(Chunk(
                id=uuid.uuid4(), video_id=video.id, index=idx,
                start_time=start, duration=duration,
                status=ChunkStatus.PENDING, priority=float(idx),
                raw_storage_path=raw_key,
            ))
            start += duration
        db.commit()

        schedule_chunks.delay(video_id)

    except Exception as exc:
        db.rollback()
        video = db.query(Video).filter(Video.id == uuid.UUID(video_id)).first()
        if video:
            video.status = VideoStatus.FAILED
            db.commit()
        job = update_job_progress(db, uuid.UUID(job_id), progress=0.0, status=JobStatus.FAILED)
        if job:
            job.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="schedule_chunks")
def schedule_chunks(video_id: str):
    """
    Fills any free processing slots for this video with the lowest-priority
    PENDING chunks. This is the only place chunk work gets dispatched to
    Celery — everything else (uploads, seeks, chunk completions) just calls
    this again, so re-prioritization always takes effect on the next tick
    rather than requiring us to reach into an already-populated queue.
    """
    db = SessionLocal()
    try:
        processing_count = (
            db.query(func.count(Chunk.id))
            .filter(Chunk.video_id == uuid.UUID(video_id), Chunk.status == ChunkStatus.PROCESSING)
            .scalar()
        )
        free_slots = settings.MAX_CONCURRENT_CHUNKS - processing_count
        if free_slots <= 0:
            return

        next_chunks = (
            db.query(Chunk)
            .filter(Chunk.video_id == uuid.UUID(video_id), Chunk.status == ChunkStatus.PENDING)
            .order_by(Chunk.priority.asc())
            .limit(free_slots)
            .all()
        )
        if not next_chunks:
            return

        # Mark them PROCESSING before dispatch so a schedule_chunks call that
        # races with this one won't double-dispatch the same chunk.
        for chunk in next_chunks:
            chunk.status = ChunkStatus.PROCESSING
        db.commit()

        for chunk in next_chunks:
            process_chunk_task.delay(video_id, str(chunk.id))
    finally:
        db.close()


@celery_app.task(bind=True, name="process_chunk_task")
def process_chunk_task(self, video_id: str, chunk_id: str):
    db = SessionLocal()
    try:
        chunk = db.query(Chunk).filter(Chunk.id == uuid.UUID(chunk_id)).first()
        if not chunk or chunk.status == ChunkStatus.COMPLETED:
            return  # already done (or gone) — never reprocess

        work_dir = tempfile.mkdtemp(prefix=f"chunk_{chunk_id}_")
        local_raw = os.path.join(work_dir, "chunk.mp4")
        storage.download_file(chunk.raw_storage_path, local_raw)

        # Filter the cached, globally-detected flagged words down to this
        # chunk's own [start, start+duration) window, shifted to be
        # relative to this chunk's own audio track (t=0).
        all_flagged = transcript_cache.load_flagged_words(video_id)
        chunk_end = chunk.start_time + chunk.duration
        words_in_chunk = [
            WordTiming(
                index=w["index"], word=w["word"],
                start=max(0.0, w["start"] - chunk.start_time),
                end=min(chunk.duration, w["end"] - chunk.start_time),
            )
            for w in all_flagged
            if w["start"] < chunk_end and w["end"] > chunk.start_time
        ]

        # Audio: extract straight from this chunk's own file (guarantees sync
        # with this chunk's own frames), beep the flagged spans if any.
        chunk_audio_raw = os.path.join(work_dir, "audio_raw.wav")
        extract_audio(local_raw, chunk_audio_raw)
        if words_in_chunk:
            chunk_audio_final = os.path.join(work_dir, "audio_beeped.wav")
            beep_censor_audio(chunk_audio_raw, words_in_chunk, chunk_audio_final)
        else:
            chunk_audio_final = chunk_audio_raw

        # Visual censorship + re-encode with the (possibly beeped) audio.
        chunk_result = process_chunk(
            local_raw, work_dir,
            sample_rate=settings.FRAME_SAMPLE_RATE,
            audio_override=chunk_audio_final,
        )

        from app.models.detection import Detection as DetectionModel
        for det in chunk_result["detections"]:
            db.add(DetectionModel(
                id=uuid.uuid4(), video_id=uuid.UUID(video_id),
                timestamp=chunk.start_time,
                category=det.category, confidence=det.confidence,
                x1=det.x1, y1=det.y1, x2=det.x2, y2=det.y2,
            ))

        # HLS-ify this chunk, upload its segments under a chunk-scoped name
        # so segments from different chunks can never collide, and record
        # them on the Chunk row — the manifest endpoint reads this directly.
        hls_dir = os.path.join(work_dir, "hls")
        os.makedirs(hls_dir, exist_ok=True)
        to_hls(chunk_result["output_path"], hls_dir)

        segments = []
        with open(os.path.join(hls_dir, "index.m3u8")) as f:
            pending_duration = None
            for line in f:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    pending_duration = float(line.split(":")[1].rstrip(","))
                elif line.endswith(".ts"):
                    new_name = f"segment_{chunk.index:04d}_{len(segments):02d}.ts"
                    os.rename(os.path.join(hls_dir, line), os.path.join(hls_dir, new_name))
                    storage.upload_file(
                        os.path.join(hls_dir, new_name),
                        storage.object_path(video_id, "output", new_name),
                    )
                    segments.append({"filename": new_name, "duration": pending_duration})

        chunk.status = ChunkStatus.COMPLETED
        chunk.hls_segments = segments
        db.commit()

        # If every chunk for this video is now done, mark the video complete.
        remaining = (
            db.query(func.count(Chunk.id))
            .filter(Chunk.video_id == uuid.UUID(video_id), Chunk.status != ChunkStatus.COMPLETED)
            .scalar()
        )
        if remaining == 0:
            video = db.query(Video).filter(Video.id == uuid.UUID(video_id)).first()
            if video:
                video.status = VideoStatus.COMPLETED
                db.commit()

    except Exception as exc:
        db.rollback()
        chunk = db.query(Chunk).filter(Chunk.id == uuid.UUID(chunk_id)).first()
        if chunk:
            chunk.status = ChunkStatus.FAILED
            chunk.error = str(exc)
            db.commit()
        raise
    finally:
        # Whether this chunk succeeded or failed, a slot just freed up —
        # let the scheduler fill it with whatever's next in priority order.
        schedule_chunks.delay(video_id)
        db.close()
