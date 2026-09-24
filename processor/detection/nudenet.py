"""
NudeNet-backed nudity detector.

The rest of the pipeline only depends on BaseDetector. NudeNet is optional:
if the package or weights are missing, detect() returns [] so chunks still
process (no visual censorship) instead of crashing the worker.
"""
from detection.base import BaseDetector, Detection

try:
    from nudenet import NudeDetector
except ImportError:
    NudeDetector = None

UNSAFE_CLASSES = {
    "EXPOSED_BREAST_F",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BUTTOCKS",
}

CONFIDENCE_THRESHOLD = 0.5


class NudeNetDetector(BaseDetector):
    def __init__(self, model_path: str = None):
        self._model = None
        if NudeDetector is None:
            return
        try:
            self._model = NudeDetector(model_path) if model_path else NudeDetector()
        except Exception:
            self._model = None

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            return []

        raw = self._model.detect(frame)
        results = []
        for item in raw:
            if item["class"] not in UNSAFE_CLASSES:
                continue
            if item["score"] < CONFIDENCE_THRESHOLD:
                continue
            x1, y1, w, h = item["box"]
            results.append(Detection(
                category=item["class"].lower(),
                confidence=float(item["score"]),
                x1=int(x1), y1=int(y1), x2=int(x1 + w), y2=int(y1 + h),
            ))
        return results
