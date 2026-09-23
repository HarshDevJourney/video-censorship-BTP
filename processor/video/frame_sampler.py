"""Extracts every Nth frame from a chunk for ML detection, instead of every frame."""
import cv2


def sample_frames(chunk_path: str, sample_rate: int = 10):
    """
    Yields (frame_index, frame_ndarray) for every `sample_rate`-th frame in the chunk.
    frame_index is the absolute index within the chunk (0-based).
    """
    cap = cv2.VideoCapture(chunk_path)
    idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % sample_rate == 0:
                yield idx, frame
            idx += 1
    finally:
        cap.release()


def get_fps(chunk_path: str) -> float:
    cap = cv2.VideoCapture(chunk_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return fps


def iterate_all_frames(chunk_path: str):
    """Yields (frame_index, frame_ndarray) for every frame — used at encode time
    so every frame gets a (tracked or detected) censorship region applied."""
    cap = cv2.VideoCapture(chunk_path)
    idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            yield idx, frame
            idx += 1
    finally:
        cap.release()
