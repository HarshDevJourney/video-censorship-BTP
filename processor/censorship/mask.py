"""Alternative censorship mode: solid black box."""
import cv2


def black_box_regions(frame, boxes):
    for (x1, y1, x2, y2) in boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
    return frame
