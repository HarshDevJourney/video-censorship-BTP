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
            print("[NudeNet] nudenet package not installed.")
            return

        try:
            self._model = NudeDetector(model_path) if model_path else NudeDetector()
        except Exception:
            self._model = None

    def detect(self, frame) -> list[Detection]:
        if self._model is None:
            return []

        try:
            raw = self._model.detect(frame)

        except Exception as exc:
            print(f"[NudeNet] Detection failed: {exc}")
            return []

        results = []

        for item in raw:
            category = item.get("class")
            confidence = float(item.get("score", 0.0))
            box = item.get("box")

            if category not in UNSAFE_CLASSES:
                continue

            if confidence < CONFIDENCE_THRESHOLD:
                continue

            if not box or len(box) != 4:
                continue

            x, y, width, height = box

            results.append(
                Detection(
                    category=category.lower(),
                    confidence=confidence,
                    x1=int(x),
                    y1=int(y),
                    x2=int(x + width),
                    y2=int(y + height),
                )
            )
            
        return results
