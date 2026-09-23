"""
NudeNet-backed nudity detector.

Swap the body of `detect()` for the real NudeNet call once the model is
vendored in (e.g. `from nudenet import NudeDetector`). Kept as a thin
adapter so the rest of the pipeline never depends on NudeNet's own
output format directly.
"""
from detection.base import BaseDetector, Detection

UNSAFE_CLASSES = {
    "EXPOSED_BREAST_F",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BUTTOCKS",
}

CONFIDENCE_THRESHOLD = 0.5


class NudeNetDetector(BaseDetector):
    def __init__(self, model_path: str = None):
        # from nudenet import NudeDetector
        # self._model = NudeDetector(model_path)
        self._model = None  # placeholder until the model is wired in

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            return []  # no-op until a real model is configured

        raw = self._model.detect(frame)  # NudeNet's native output
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
