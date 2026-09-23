"""MinIO wrapper for object storage: original videos, chunks, and HLS output."""
import io
from minio import Minio

from app.core.config import settings

client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def ensure_bucket():
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def upload_file(local_path: str, object_name: str) -> str:
    ensure_bucket()
    client.fput_object(settings.MINIO_BUCKET, object_name, local_path)
    return object_name


def upload_bytes(data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    ensure_bucket()
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def download_file(object_name: str, local_path: str):
    client.fget_object(settings.MINIO_BUCKET, object_name, local_path)


def object_path(video_id: str, *parts: str) -> str:
    return "/".join([str(video_id), *parts])
