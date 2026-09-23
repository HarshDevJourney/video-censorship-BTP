"""Applies a Gaussian blur to the given regions of a frame."""
import cv2


def blur_regions(frame, boxes, strength: int = 35):
    h, w = frame.shape[:2]
    for (x1, y1, x2, y2) in boxes:
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        roi = frame[y1:y2, x1:x2]
        k = strength if strength % 2 == 1 else strength + 1
        blurred = cv2.GaussianBlur(roi, (k, k), 0)
        frame[y1:y2, x1:x2] = blurred
    return frame
