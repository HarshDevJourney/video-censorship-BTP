"""
Lightweight IOU-based tracker used to carry a detected unsafe region across
frames where the detector didn't run (frame sampling) or momentarily missed
a detection, so censorship doesn't flicker.

This is a simple placeholder — swap for ByteTrack or another multi-object
tracker for more robust behavior on fast motion / occlusion.
"""
from dataclasses import dataclass, field


@dataclass
class Track:
    track_id: int
    category: str
    box: tuple  # (x1, y1, x2, y2)
    misses: int = 0


def iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


class RegionTracker:
    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 15):
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self._tracks: list[Track] = []
        self._next_id = 1

    def update(self, detections):
        """detections: list of Detection (may be empty on non-sampled frames).
        Returns the current list of active boxes to censor this frame."""
        if detections:
            matched_track_ids = set()
            for det in detections:
                det_box = (det.x1, det.y1, det.x2, det.y2)
                best_track, best_iou = None, 0.0
                for track in self._tracks:
                    score = iou(track.box, det_box)
                    if score > best_iou:
                        best_track, best_iou = track, score

                if best_track and best_iou >= self.iou_threshold:
                    best_track.box = det_box
                    best_track.misses = 0
                    matched_track_ids.add(best_track.track_id)
                else:
                    new_track = Track(track_id=self._next_id, category=det.category, box=det_box)
                    self._next_id += 1
                    self._tracks.append(new_track)
                    matched_track_ids.add(new_track.track_id)

            for track in self._tracks:
                if track.track_id not in matched_track_ids:
                    track.misses += 1
        else:
            # No detector run this frame — age out existing tracks, keep the rest alive
            for track in self._tracks:
                track.misses += 1

        self._tracks = [t for t in self._tracks if t.misses <= self.max_misses]
        return [t.box for t in self._tracks]
