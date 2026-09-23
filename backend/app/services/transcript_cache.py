"""
Caches the (expensive) whole-video Whisper transcription + Claude profanity
detection as a JSON blob in MinIO, keyed by video_id. Computed once in
prepare_video(); every chunk task just loads this and filters to its own
time window, instead of re-transcribing per chunk.
"""
import json
import io

from app.services import storage

FLAGGED_WORDS_FILENAME = "audio_flagged_words.json"


def save_flagged_words(video_id, flagged_words: list[dict]):
    """flagged_words: list of {"index": int, "word": str, "start": float, "end": float}"""
    key = storage.object_path(video_id, FLAGGED_WORDS_FILENAME)
    payload = json.dumps(flagged_words).encode("utf-8")
    storage.upload_bytes(payload, key, content_type="application/json")
    return key


def load_flagged_words(video_id) -> list[dict]:
    key = storage.object_path(video_id, FLAGGED_WORDS_FILENAME)
    try:
        response = storage.client.get_object(storage.settings.MINIO_BUCKET, key)
        return json.loads(response.read())
    except Exception:
        return []
