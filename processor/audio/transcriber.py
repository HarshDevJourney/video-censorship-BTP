"""
Speech-to-text with word-level timestamps, used to locate candidate words
in time before the AI profanity pass decides which ones to censor.

Uses faster-whisper (CTranslate2-based Whisper) for speed. Swap the model
size via the WHISPER_MODEL env var (tiny/base/small/medium/large-v3).
"""
import os
from dataclasses import dataclass

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        try:
            _model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
        except Exception:
            _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


@dataclass
class WordTiming:
    index: int
    word: str
    start: float
    end: float


def transcribe_with_word_timestamps(audio_path: str) -> list[WordTiming]:
    """Returns a flat, sequentially-indexed list of WordTiming across the
    whole audio file. The `index` field is what the AI detector references
    back to when it flags which words should be censored."""
    model = _get_model()
    segments, _info = model.transcribe(audio_path, word_timestamps=True)

    words: list[WordTiming] = []
    i = 0
    for segment in segments:
        for w in (segment.words or []):
            words.append(WordTiming(index=i, word=w.word.strip(), start=w.start, end=w.end))
            i += 1
    return words
