import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.job import JobStatus


class JobOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    status: JobStatus
    progress: float
    error: Optional[str] = None

    class Config:
        from_attributes = True


class JobCreatedOut(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
