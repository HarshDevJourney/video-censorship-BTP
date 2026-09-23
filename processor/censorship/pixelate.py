"""Alternative censorship mode: pixelation instead of blur."""
import cv2


def pixelate_regions(frame, boxes, block_size: int = 12):
    h, w = frame.shape[:2]
    for (x1, y1, x2, y2) in boxes:
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        roi = frame[y1:y2, x1:x2]
        small = cv2.resize(roi, (max(1, (x2 - x1) // block_size), max(1, (y2 - y1) // block_size)),
                            interpolation=cv2.INTER_LINEAR)
        frame[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    return frame
