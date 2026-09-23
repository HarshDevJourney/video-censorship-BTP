import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.video import Video, VideoStatus
from app.models.chunk import Chunk, ChunkStatus
from app.core.config import settings
from app.services import storage

router = APIRouter(prefix="/api/videos", tags=["streaming"])


@router.get("/{video_id}/stream")
async def stream_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Returns the live HLS manifest URL for this video. The user can open this
    the moment processing starts — the manifest below only lists segments
    that are actually ready, and grows as more chunks complete, so the
    player naturally buffers on not-yet-processed sections instead of 404ing.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"manifest_url": f"/api/videos/{video_id}/manifest"}


@router.get("/{video_id}/manifest")
async def get_manifest(video_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Builds an HLS playlist on the fly from whichever chunks are COMPLETED
    right now. Uses PLAYLIST-TYPE:EVENT (segments only ever get appended,
    never removed/reordered) until the whole video is done, at which point
    it becomes a normal closed VOD playlist. Player polls this endpoint
    every few seconds while the video is still processing.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    completed_chunks = (
        db.query(Chunk)
        .filter(Chunk.video_id == video_id, Chunk.status == ChunkStatus.COMPLETED)
        .order_by(Chunk.index.asc())
        .all()
    )

    is_fully_done = video.status == VideoStatus.COMPLETED
    playlist_type = "VOD" if is_fully_done else "EVENT"

    max_seg_duration = 6
    for c in completed_chunks:
        for seg in (c.hls_segments or []):
            max_seg_duration = max(max_seg_duration, int(seg["duration"]) + 1)

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-PLAYLIST-TYPE:{playlist_type}",
        f"#EXT-X-TARGETDURATION:{max_seg_duration}",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]

    # NOTE: only chunks that are COMPLETED contribute segments. A chunk that
    # hasn't been reached yet simply has no entry — this is what makes
    # "jump ahead, wait a moment for it to catch up" work: the player sees
    # a playlist that currently ends before the seek target, buffers, and
    # a re-fetch a few seconds later (once that chunk finishes) reveals it.
    for chunk in completed_chunks:
        for seg in (chunk.hls_segments or []):
            key = storage.object_path(video_id, "output", seg["filename"])
            url = storage.client.presigned_get_object(settings.MINIO_BUCKET, key)
            lines.append(f"#EXTINF:{seg['duration']:.3f},")
            lines.append(url)

    if is_fully_done:
        lines.append("#EXT-X-ENDLIST")

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="application/vnd.apple.mpegurl")
