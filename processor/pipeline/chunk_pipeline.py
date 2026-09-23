"""Processes a single chunk: sample frames -> detect -> track -> censor every frame -> re-encode."""
import os
import uuid
import cv2

from video.frame_sampler import sample_frames, iterate_all_frames, get_fps
from detection.detector import MultiDetector
from detection.base import Detection
from tracking.tracker import RegionTracker
from censorship.blur import blur_regions
from utils.ffmpeg import encode_frames_to_video


def process_chunk(chunk_path: str, work_dir: str, sample_rate: int = 10,
                   audio_override: str = None) -> dict:
    """
    Returns {"output_path": ..., "detections": [Detection, ...]} where detections
    are timestamped relative to the chunk (caller offsets them to the full video).
    """
    fps = get_fps(chunk_path)
    detector = MultiDetector()
    tracker = RegionTracker()

    # Pass 1: run detection on sampled frames only, feeding the tracker as we go,
    # so we know which boxes are "active" at any given frame index.
    sampled_detections = {}  # frame_idx -> list[Detection]
    for idx, frame in sample_frames(chunk_path, sample_rate):
        sampled_detections[idx] = detector.detect(frame)

    all_detections: list[Detection] = []
    for dets in sampled_detections.values():
        all_detections.extend(dets)

    # Pass 2: walk every frame, updating/consulting the tracker, and censor.
    frames_dir = os.path.join(work_dir, f"censored_frames_{uuid.uuid4().hex[:8]}")
    os.makedirs(frames_dir, exist_ok=True)

    for idx, frame in iterate_all_frames(chunk_path):
        dets = sampled_detections.get(idx)  # None on non-sampled frames
        boxes = tracker.update(dets if dets is not None else [])
        if boxes:
            frame = blur_regions(frame, boxes)
        cv2.imwrite(os.path.join(frames_dir, f"frame_{idx:06d}.png"), frame)

    # Use the profanity-censored audio slice for this chunk if one was provided
    # (see pipeline/video_pipeline.py), otherwise fall back to the chunk's own audio.
    audio_source = audio_override or chunk_path

    output_path = os.path.join(work_dir, f"censored_{os.path.basename(chunk_path)}")
    encode_frames_to_video(frames_dir, fps=fps, output_path=output_path, audio_source=audio_source)

    return {"output_path": output_path, "detections": all_detections, "fps": fps}
