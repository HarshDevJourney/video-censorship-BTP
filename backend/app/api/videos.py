import uuid
import shutil
import tempfile
import os

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.video import Video, VideoStatus, SourceType
from app.models.chunk import Chunk, ChunkStatus
from app.schemas.video import VideoOut, YoutubeRequest
from app.schemas.job import JobCreatedOut
from app.schemas.chunk import ChunkOut, SeekRequest
from app.services.jobs import create_video_and_job
from app.services import storage
from app.workers.tasks import prepare_video, schedule_chunks

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post("/upload", response_model=JobCreatedOut)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    video_id = uuid.uuid4()

    # Save to a temp file, then push to MinIO under videos/{video_id}/original.mp4
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    object_name = storage.object_path(video_id, "original.mp4")
    storage.upload_file(tmp_path, object_name)
    os.remove(tmp_path)

    video = Video(
        id=video_id,
        source_type=SourceType.UPLOAD,
        original_filename=file.filename,
        storage_path=object_name,
        status=VideoStatus.QUEUED,
    )
    job = create_video_and_job(db, video)

    # prepare_video: transcribes audio once, splits into chunks, creates Chunk
    # rows, then kicks off the self-rescheduling chunk scheduler.
    prepare_video.delay(str(job.id), str(video.id))

    return JobCreatedOut(job_id=job.id, status=job.status)


@router.post("/youtube", response_model=JobCreatedOut)
async def submit_youtube(payload: YoutubeRequest, db: Session = Depends(get_db)):
    video_id = uuid.uuid4()

    video = Video(
        id=video_id,
        source_type=SourceType.YOUTUBE,
        source_url=payload.url,
        status=VideoStatus.QUEUED,
    )
    job = create_video_and_job(db, video)

    prepare_video.delay(str(job.id), str(video.id))

    return JobCreatedOut(job_id=job.id, status=job.status)


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/{video_id}/chunks", response_model=list[ChunkOut])
async def list_chunks(video_id: uuid.UUID, db: Session = Depends(get_db)):
    """Per-chunk status, in order — the frontend polls this to render a
    'which parts of the video are ready' buffering bar."""
    chunks = (
        db.query(Chunk)
        .filter(Chunk.video_id == video_id)
        .order_by(Chunk.index.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks yet — video may still be preparing")
    return chunks


@router.post("/{video_id}/seek")
async def seek_video(video_id: uuid.UUID, payload: SeekRequest, db: Session = Depends(get_db)):
    """
    Called when the user scrubs/jumps in the player. Re-prioritizes every
    PENDING chunk by distance from the new playhead, so chunks near where
    the user landed get processed next. Chunks already PROCESSING or
    COMPLETED are left alone — nothing already done is ever redone, and we
    don't interrupt in-flight work.
    """
    pending_chunks = (
        db.query(Chunk)
        .filter(Chunk.video_id == video_id, Chunk.status == ChunkStatus.PENDING)
        .all()
    )
    for chunk in pending_chunks:
        chunk.priority = abs(chunk.start_time - payload.timestamp)
    db.commit()

    schedule_chunks.delay(str(video_id))

    return {"reprioritized": len(pending_chunks)}
