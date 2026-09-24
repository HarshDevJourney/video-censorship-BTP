"""
Audio side of censorship — detection only.

Transcribes the FULL original video once (so Whisper/Claude have complete
sentence context) and returns the flagged words with ABSOLUTE timestamps
(seconds from the start of the whole video). It does NOT render a censored
audio track here — that happens per-chunk in video_pipeline.py, using each
chunk's own audio file, which is what keeps beeps in sync with the actual
(keyframe-aligned, non-uniform-length) video chunks.
"""
import os

from utils.ffmpeg import extract_audio
from audio.transcriber import transcribe_with_word_timestamps
from audio.ai_detector import detect_words_to_censor


def detect_profanity_for_video(video_path: str, work_dir: str) -> list:
    """Returns a list[WordTiming] (absolute timestamps) flagged for censorship.
    Returns [] on any failure — callers should treat that as "ship audio
    unmodified" rather than failing the whole job."""
    raw_audio_path = os.path.join(work_dir, "audio_full.wav")
    try:
        extract_audio(video_path, raw_audio_path)
        words = transcribe_with_word_timestamps(raw_audio_path)
        flagged_indices = detect_words_to_censor(words)
    except Exception:
        return []

    return [w for w in words if w.index in flagged_indices]
