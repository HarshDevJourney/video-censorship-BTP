"""Thin wrappers around ffmpeg-python / ffmpeg CLI for the operations the pipeline needs."""
import subprocess
import json


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    return float(data["format"]["duration"])


def split_into_chunks(input_path: str, output_dir: str, chunk_seconds: int) -> list[str]:
    """Splits input_path into fixed-length mp4 chunks using stream copy (fast, no re-encode)."""
    pattern = f"{output_dir}/chunk_%04d.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-c", "copy", "-map", "0",
            "-f", "segment", "-segment_time", str(chunk_seconds),
            "-reset_timestamps", "1",
            pattern,
        ],
        check=True, capture_output=True,
    )
    import glob
    return sorted(glob.glob(f"{output_dir}/chunk_*.mp4"))


def encode_frames_to_video(frames_dir: str, fps: float, output_path: str, audio_source: str = None):
    """Re-encodes a directory of frame_%06d.png (censored frames) back into a video,
    optionally muxing in the original audio track."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", f"{frames_dir}/frame_%06d.png",
    ]
    if audio_source:
        cmd += ["-i", audio_source, "-map", "0:v:0", "-map", "1:a:0?"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", output_path]
    subprocess.run(cmd, check=True, capture_output=True)


def extract_audio(input_path: str, output_path: str):
    """Pulls the audio track out of a video into a standalone wav file."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "44100", "-ac", "2", output_path],
        check=True, capture_output=True,
    )
    return output_path


def slice_audio(audio_path: str, start_seconds: float, duration_seconds: float, output_path: str):
    """Extracts a [start, start+duration) slice from an audio file — used to line up
    the full-video censored audio track with each chunk's video."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path,
         "-ss", str(start_seconds), "-t", str(duration_seconds),
         "-acodec", "pcm_s16le", output_path],
        check=True, capture_output=True,
    )
    return output_path


def to_hls(input_path: str, output_dir: str, segment_seconds: int = 6):
    """Converts a processed mp4 chunk/video into an HLS playlist + .ts segments."""
    playlist = f"{output_dir}/index.m3u8"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "h264", "-c:a", "aac",
            "-hls_time", str(segment_seconds),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{output_dir}/segment_%04d.ts",
            playlist,
        ],
        check=True, capture_output=True,
    )
    return playlist
