from dataclasses import dataclass


@dataclass
class Detection:
    category: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


class BaseDetector:
    """Common interface every detector (nudity, violence, blood) implements."""

    def detect(self, frame) -> list[Detection]:
        raise NotImplementedError
