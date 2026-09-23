"""
Top-level orchestration: chunk the source video, process each chunk
(detect -> track -> censor -> encode), convert each processed chunk to HLS
segments, stitch a master playlist, upload everything to MinIO, and persist
detections to Postgres. Called from the Celery task in backend/app/workers/tasks.py.
"""
import os
import tempfile
import uuid

from video.chunker import chunk_video
from pipeline.chunk_pipeline import process_chunk
from pipeline.audio_pipeline import run_audio_pipeline
from utils.ffmpeg import probe_duration, to_hls, slice_audio

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from app.services import storage  # noqa: E402
from app.models.detection import Detection as DetectionModel  # noqa: E402

CHUNK_SECONDS = int(os.environ.get("CHUNK_SECONDS", 10))
FRAME_SAMPLE_RATE = int(os.environ.get("FRAME_SAMPLE_RATE", 10))


def run_video_pipeline(db, video_id: str, input_path: str, progress_cb=None) -> dict:
    duration = probe_duration(input_path)
    work_dir = tempfile.mkdtemp(prefix=f"vc_{video_id}_")

    # Audio: transcribe + beep/mute profanity across the whole video once,
    # up front, so profanity detection has full sentence context rather than
    # being run separately (and possibly split awkwardly) per chunk.
    audio_result = run_audio_pipeline(input_path, work_dir)
    censored_audio_path = audio_result["censored_audio_path"]

    chunks = chunk_video(input_path, work_dir, chunk_seconds=CHUNK_SECONDS)
    total_chunks = len(chunks)

    playlist_entries = []  # ordered list of (chunk_index, local_hls_dir)

    for i, chunk_path in enumerate(chunks):
        # Slice the matching window out of the full censored audio track so
        # each chunk gets its own (already-censored) audio when re-encoded.
        chunk_start = i * CHUNK_SECONDS
        chunk_audio_slice = os.path.join(work_dir, f"audio_chunk_{i:04d}.wav")
        slice_audio(censored_audio_path, chunk_start, CHUNK_SECONDS, chunk_audio_slice)

        chunk_result = process_chunk(
            chunk_path, work_dir,
            sample_rate=FRAME_SAMPLE_RATE,
            audio_override=chunk_audio_slice,
        )

        # Offset detection timestamps by this chunk's start time and persist them.
        chunk_start_time = i * CHUNK_SECONDS
        for det in chunk_result["detections"]:
            db.add(DetectionModel(
                id=uuid.uuid4(),
                video_id=video_id,
                timestamp=chunk_start_time,  # refine with per-frame offset if needed
                category=det.category,
                confidence=det.confidence,
                x1=det.x1, y1=det.y1, x2=det.x2, y2=det.y2,
            ))
        db.commit()

        # Convert the censored chunk to its own HLS segment set.
        hls_dir = os.path.join(work_dir, f"hls_{i:04d}")
        os.makedirs(hls_dir, exist_ok=True)
        to_hls(chunk_result["output_path"], hls_dir)
        playlist_entries.append((i, hls_dir))

        if progress_cb:
            progress_cb(round(((i + 1) / total_chunks) * 95, 1))

    master_path = _stitch_master_playlist(video_id, playlist_entries, work_dir)
    _upload_hls_output(video_id, work_dir, master_path)

    if progress_cb:
        progress_cb(100.0)

    return {"duration": duration, "chunks": total_chunks, "profanity_hits": len(audio_result["hits"])}


def _stitch_master_playlist(video_id: str, playlist_entries, work_dir: str) -> str:
    """Concatenates per-chunk HLS playlists into one ordered VOD playlist,
    renumbering segments so ordering survives out-of-order chunk completion."""
    master_path = os.path.join(work_dir, "master.m3u8")
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-PLAYLIST-TYPE:VOD", "#EXT-X-TARGETDURATION:6"]

    seg_counter = 0
    for chunk_idx, hls_dir in sorted(playlist_entries, key=lambda t: t[0]):
        chunk_playlist = os.path.join(hls_dir, "index.m3u8")
        with open(chunk_playlist) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    lines.append(line)
                elif line.endswith(".ts"):
                    new_name = f"segment_{seg_counter:04d}.ts"
                    os.rename(os.path.join(hls_dir, line), os.path.join(work_dir, new_name))
                    lines.append(new_name)
                    seg_counter += 1

    lines.append("#EXT-X-ENDLIST")
    with open(master_path, "w") as f:
        f.write("\n".join(lines))
    return master_path


def _upload_hls_output(video_id: str, work_dir: str, master_path: str):
    storage.upload_file(master_path, storage.object_path(video_id, "output", "master.m3u8"))
    for fname in os.listdir(work_dir):
        if fname.endswith(".ts"):
            storage.upload_file(
                os.path.join(work_dir, fname),
                storage.object_path(video_id, "output", fname),
            )
