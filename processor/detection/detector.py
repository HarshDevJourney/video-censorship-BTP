"""
Runs all configured detectors on a frame
and merges their outputs.
"""

from detection.nudenet import NudeNetDetector
from detection.violence import ViolenceDetector
from detection.blood import BloodDetector


class MultiDetector:

    def __init__(
        self,
        nudenet_model_path: str = None,
        violence_model_path: str = None,
        blood_model_path: str = "models/blood.pt",
    ):

        self.detectors = [
            NudeNetDetector(
                model_path=nudenet_model_path
            ),

            ViolenceDetector(
                model_path=violence_model_path
            ),

            BloodDetector(
                model_path=blood_model_path
            ),
        ]

    def detect(self, frame):

        results = []

        for detector in self.detectors:

            try:
                results.extend(
                    detector.detect(frame)
                )

            except Exception as exc:
                print(
                    f"[MultiDetector] "
                    f"{detector.__class__.__name__} "
                    f"failed: {exc}"
                )

        return results