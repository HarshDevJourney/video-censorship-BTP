import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.chunk import Chunk, ChunkStatus
from app.schemas.job import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Progress is derived live from chunk completion — there's no single
    # "process_video" task writing a percentage anymore, since chunks
    # complete independently and out of order.
    total = db.query(Chunk).filter(Chunk.video_id == job.video_id).count()
    if total > 0:
        completed = (
            db.query(Chunk)
            .filter(Chunk.video_id == job.video_id, Chunk.status == ChunkStatus.COMPLETED)
            .count()
        )
        failed = (
            db.query(Chunk)
            .filter(Chunk.video_id == job.video_id, Chunk.status == ChunkStatus.FAILED)
            .count()
        )
        job.progress = round((completed / total) * 100, 1)
        if failed and completed + failed == total:
            job.status = JobStatus.FAILED
        elif completed == total:
            job.status = JobStatus.COMPLETED
        elif completed > 0 or db.query(Chunk).filter(
            Chunk.video_id == job.video_id, Chunk.status == ChunkStatus.PROCESSING
        ).count() > 0:
            job.status = JobStatus.RUNNING

    return job
