"""
YOLO-based blood/gore detector.

Expected model:

    models/blood.pt

The model should be trained to detect blood/gore-related
visual content.
"""

from detection.base import BaseDetector, Detection

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


CONFIDENCE_THRESHOLD = 0.5


class BloodDetector(BaseDetector):

    def __init__(
        self,
        model_path: str = "models/blood.pt",
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self._model = None
        self.confidence_threshold = confidence_threshold

        if YOLO is None:
            print("[Blood] ultralytics package not installed.")
            return

        try:
            self._model = YOLO(model_path)

            print(
                f"[Blood] Model loaded: {model_path}"
            )

        except Exception as exc:
            print(
                f"[Blood] Failed to load model: {exc}"
            )

            self._model = None

    def detect(self, frame) -> list[Detection]:

        if self._model is None:
            return []

        if frame is None:
            return []

        try:
            predictions = self._model.predict(
                source=frame,
                conf=self.confidence_threshold,
                verbose=False,
            )

        except Exception as exc:
            print(
                f"[Blood] Detection failed: {exc}"
            )
            return []

        results = []

        for prediction in predictions:

            if prediction.boxes is None:
                continue

            names = prediction.names

            for box in prediction.boxes:

                confidence = float(
                    box.conf[0].item()
                )

                class_id = int(
                    box.cls[0].item()
                )

                category = names[class_id]

                x1, y1, x2, y2 = (
                    box.xyxy[0]
                    .tolist()
                )

                results.append(
                    Detection(
                        category=category.lower(),
                        confidence=confidence,
                        x1=int(x1),
                        y1=int(y1),
                        x2=int(x2),
                        y2=int(y2),
                    )
                )

        return results