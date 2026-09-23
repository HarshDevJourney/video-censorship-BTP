"""
One row per video chunk. This table IS the priority queue: instead of
dumping every chunk into Celery/Redis up front (which is hard to reorder),
we keep every chunk's status + priority here and let a self-rescheduling
Celery task (schedule_chunks) pull the next lowest-priority `pending` chunk
whenever a slot frees up. Seeking just updates `priority`; nothing already
`completed` is ever touched again.
"""
import uuid
import enum
from sqlalchemy import Column, Float, Integer, String, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ChunkStatus(str, enum.Enum):
    PENDING = "pending"       # not started yet, waiting for a free slot
    PROCESSING = "processing"  # currently running in a Celery worker
    COMPLETED = "completed"    # HLS segments uploaded, safe to serve, never reprocessed
    FAILED = "failed"


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)

    index = Column(Integer, nullable=False)          # order in the video, 0-based
    start_time = Column(Float, nullable=False)        # real (probed) start, seconds
    duration = Column(Float, nullable=False)           # real (probed) duration, seconds

    status = Column(Enum(ChunkStatus), default=ChunkStatus.PENDING, nullable=False, index=True)
    # Lower = processed sooner. Defaults to `index` (sequential from the start).
    # A seek to timestamp T sets this to abs(start_time - T) for every PENDING
    # chunk, so chunks nearest the new playhead jump to the front of the line.
    priority = Column(Float, nullable=False, default=0.0, index=True)

    raw_storage_path = Column(String, nullable=True)   # MinIO key: the unprocessed chunk
    # [{"filename": "segment_0000_00.ts", "duration": 5.8}, ...] once completed
    hls_segments = Column(JSONB, nullable=True)

    error = Column(Text, nullable=True)
