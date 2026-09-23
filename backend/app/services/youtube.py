"""Downloads a YouTube video to a local temp path using yt-dlp."""
import tempfile
import os
import yt_dlp


def download_youtube_video(url: str) -> str:
    """Downloads the video and returns the local file path (mp4)."""
    tmp_dir = tempfile.mkdtemp(prefix="ytdl_")
    out_path = os.path.join(tmp_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": out_path,
        "format": "mp4/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return filename
