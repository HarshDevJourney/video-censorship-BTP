"""Placeholder violence detector — swap in a real classifier/localizer later.
Keeps the same BaseDetector interface as nudenet.py so the merger doesn't care."""
from detection.base import BaseDetector, Detection


class ViolenceDetector(BaseDetector):
    def __init__(self, model_path: str = None):
        self._model = None

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            return []
        # raw = self._model.predict(frame) ...
        return []
