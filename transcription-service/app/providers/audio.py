"""Audio extraction + chunking for tier 2.

Uses yt-dlp to pull the best audio track, then ffmpeg to split it into
fixed-length chunks below the typical 25 MB / ~15-minute STT request ceiling
(the limit the PDF highlights for cloud Whisper). Local Whisper has no such
limit, but chunking keeps memory bounded and lets segment offsets be
reconstructed deterministically.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from app.config import get_settings
from app.proxy import get_ytdlp_proxy_url


@dataclass
class AudioChunk:
    path: str
    offset_s: float  # start offset of this chunk within the full audio


def download_audio(video_id: str, dest_dir: str) -> str:
    """Download bestaudio as a wav file and return its path."""
    from yt_dlp import YoutubeDL

    os.makedirs(dest_dir, exist_ok=True)
    out_template = os.path.join(dest_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
        ],
    }
    proxy_url = get_ytdlp_proxy_url()
    if proxy_url:
        ydl_opts["proxy"] = proxy_url

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    wav_path = os.path.join(dest_dir, f"{video_id}.wav")
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"expected audio at {wav_path}")
    return wav_path


def split_audio(wav_path: str, chunk_seconds: int | None = None) -> list[AudioChunk]:
    """Split a wav into ≤``chunk_seconds`` pieces via ffmpeg segment muxer."""
    chunk_seconds = chunk_seconds or get_settings().audio_chunk_seconds
    base, _ = os.path.splitext(wav_path)
    pattern = f"{base}_chunk_%03d.wav"

    subprocess.run(
        [
            "ffmpeg", "-i", wav_path,
            "-f", "segment", "-segment_time", str(chunk_seconds),
            "-c", "copy", "-reset_timestamps", "1", pattern,
            "-loglevel", "error",
        ],
        check=True,
    )

    chunks: list[AudioChunk] = []
    idx = 0
    while True:
        path = f"{base}_chunk_{idx:03d}.wav"
        if not os.path.exists(path):
            break
        chunks.append(AudioChunk(path=path, offset_s=idx * chunk_seconds))
        idx += 1

    # Single-file (shorter than chunk size) case: ffmpeg still emits _chunk_000.
    return chunks
