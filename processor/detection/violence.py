"""
YOLO-based violence detector.

Expected model:

    models/violence.pt

The model should be trained for the violence-related
classes that your project wants to censor.
"""

import os

from detection.base import BaseDetector, Detection

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


CONFIDENCE_THRESHOLD = 0.5


class ViolenceDetector(BaseDetector):

    def __init__(
        self,
        model_path: str = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self._model = None
        self.confidence_threshold = confidence_threshold

        if model_path is None:
            model_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "models", "violence.pt")
            )

        if YOLO is None:
            print("[Violence] ultralytics package not installed.")
            return

        try:
            self._model = YOLO(model_path)

            print(
                f"[Violence] Model loaded: {model_path}"
            )

        except Exception as exc:
            print(
                f"[Violence] Failed to load model: {exc}"
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
                f"[Violence] Detection failed: {exc}"
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