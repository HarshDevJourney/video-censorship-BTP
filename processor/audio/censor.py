"""Overlays a beep tone over the given word timings in an audio file."""
from pydub import AudioSegment
from pydub.generators import Sine

from audio.transcriber import WordTiming


def beep_censor_audio(audio_path: str, words_to_censor: list[WordTiming], output_path: str,
                       beep_freq: int = 1000, padding_ms: int = 60) -> str:
    """
    words_to_censor: the WordTiming entries the AI detector flagged.
    padding_ms: extra time beeped on each side of a word, so the beep fully
    covers the sound and doesn't clip at the edges.
    """
    audio = AudioSegment.from_file(audio_path)

    for w in words_to_censor:
        start_ms = max(0, int(w.start * 1000) - padding_ms)
        end_ms = min(len(audio), int(w.end * 1000) + padding_ms)
        if end_ms <= start_ms:
            continue

        duration_ms = end_ms - start_ms
        beep = Sine(beep_freq).to_audio_segment(duration=duration_ms).apply_gain(-3)
        audio = audio[:start_ms] + beep + audio[end_ms:]

    audio.export(output_path, format="wav")
    return output_path
