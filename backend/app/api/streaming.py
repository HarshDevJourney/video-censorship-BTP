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

    # Do not publish a later chunk before an earlier one is ready. HLS would
    # otherwise play the later chunk at the wrong timeline position, then
    # jump backwards whenever the missing chunk completes.
    contiguous_chunks = []
    expected_index = 0
    for chunk in completed_chunks:
        if chunk.index != expected_index:
            break
        contiguous_chunks.append(chunk)
        expected_index += 1

    is_fully_done = video.status == VideoStatus.COMPLETED
    playlist_type = "VOD" if is_fully_done else "EVENT"

    max_seg_duration = 6
    for c in contiguous_chunks:
        for seg in (c.hls_segments or []):
            max_seg_duration = max(max_seg_duration, int(seg["duration"]) + 1)

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-PLAYLIST-TYPE:{playlist_type}",
        f"#EXT-X-TARGETDURATION:{max_seg_duration}",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]

    # Serve segments through the API so the browser never has to talk to the
    # internal MinIO hostname (minio:9000) used by the containers.
    for i, chunk in enumerate(contiguous_chunks):
        if i > 0:
            lines.append("#EXT-X-DISCONTINUITY")
        for seg in (chunk.hls_segments or []):
            lines.append(f"#EXTINF:{seg['duration']:.3f},")
            lines.append(f"/api/videos/{video_id}/hls/{seg['filename']}")

    if is_fully_done:
        lines.append("#EXT-X-ENDLIST")

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="application/vnd.apple.mpegurl")


@router.get("/{video_id}/hls/{filename}")
async def get_hls_segment(video_id: uuid.UUID, filename: str):
    """Proxy HLS segments from MinIO so the browser can fetch them from the API."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    key = storage.object_path(video_id, "output", filename)
    try:
        obj = storage.client.get_object(settings.MINIO_BUCKET, key)
        try:
            data = obj.read()
        finally:
            obj.close()
            obj.release_conn()
    except Exception:
        raise HTTPException(status_code=404, detail="Segment not found")
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/MP2T"
    return Response(content=data, media_type=media_type)
