"""Runs all configured detectors on a frame and merges their outputs."""
from detection.nudenet import NudeNetDetector
from detection.violence import ViolenceDetector
from detection.blood import BloodDetector


class MultiDetector:
    def __init__(self):
        self.detectors = [
            NudeNetDetector(),
            ViolenceDetector(),
            BloodDetector(),
        ]

    def detect(self, frame):
        results = []
        for d in self.detectors:
            results.extend(d.detect(frame))
        return results
