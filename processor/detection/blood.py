"""Placeholder blood/gore detector — same interface as the others."""
from detection.base import BaseDetector, Detection


class BloodDetector(BaseDetector):
    def __init__(self, model_path: str = None):
        self._model = None

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            return []
        return []
