"""Splits a source video into fixed-length chunks for parallel/streamed processing."""
import os
from utils.ffmpeg import split_into_chunks


def chunk_video(input_path: str, work_dir: str, chunk_seconds: int = 10) -> list[str]:
    chunks_dir = os.path.join(work_dir, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    return split_into_chunks(input_path, chunks_dir, chunk_seconds)
