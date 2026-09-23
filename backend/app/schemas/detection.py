import uuid
from pydantic import BaseModel


class DetectionOut(BaseModel):
    id: uuid.UUID
    timestamp: float
    category: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    class Config:
        from_attributes = True
