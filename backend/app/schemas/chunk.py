import uuid
from pydantic import BaseModel

from app.models.chunk import ChunkStatus


class ChunkOut(BaseModel):
    index: int
    start_time: float
    duration: float
    status: ChunkStatus

    class Config:
        from_attributes = True


class SeekRequest(BaseModel):
    timestamp: float  # seconds into the video the user just jumped to
