import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.video import VideoStatus, SourceType


class VideoOut(BaseModel):
    id: uuid.UUID
    source_type: SourceType
    original_filename: Optional[str] = None
    duration: Optional[float] = None
    status: VideoStatus
    created_at: datetime

    class Config:
        from_attributes = True


class YoutubeRequest(BaseModel):
    url: str
