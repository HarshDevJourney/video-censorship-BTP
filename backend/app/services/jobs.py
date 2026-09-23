"""Helper functions for creating/updating job + video DB records."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.video import Video


def create_video_and_job(db: Session, video: Video) -> Job:
    db.add(video)
    db.flush()

    job = Job(id=uuid.uuid4(), video_id=video.id, status=JobStatus.PENDING, progress=0.0)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_progress(db: Session, job_id: uuid.UUID, progress: float, status: JobStatus = None):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None
    job.progress = progress
    if status:
        job.status = status
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return job
