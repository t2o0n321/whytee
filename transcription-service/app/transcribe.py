"""Tiered fallback orchestrator.

Mirrors lifesized/youtube-transcriber's strategy from the PDF:
  tier 1  official / auto captions (cheap, no download)
  tier 2  audio download + local Whisper STT (works when no captions exist)

The orchestrator is deliberately thin and free of network specifics so it can
be unit-tested by patching the provider functions.
"""

from __future__ import annotations

import re

from app.config import get_settings
from app.models import Segment, TranscribeResponse, TranscriptSource
from app.providers import audio, captions, elevenlabs, whisper_cloud, whisper_local, whisper_mlx

_VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([0-9A-Za-z_-]{11})")

# Tier-2 backends, each exposing ``transcribe_chunks`` and a ``SOURCE`` constant.
_STT_BACKENDS = {
    "local": whisper_local,
    "cloud": whisper_cloud,
    "elevenlabs": elevenlabs,
    "mlx": whisper_mlx,
}


def _stt_backend():
    """Return the configured tier-2 STT module (same ``transcribe_chunks`` API)."""
    return _STT_BACKENDS.get(get_settings().stt_backend, whisper_local)


def extract_video_id(video_id: str | None, url: str | None) -> str:
    """Normalise a request into a bare 11-char video id."""
    if video_id:
        return video_id
    if url:
        match = _VIDEO_ID_RE.search(url)
        if match:
            return match.group(1)
        # Bare id passed as url, or unknown format.
        if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
            return url
    raise ValueError("could not determine video id from request")


def _join_text(segments: list[Segment]) -> str:
    return " ".join(s.text.strip() for s in segments if s.text.strip())


def _total_duration(segments: list[Segment]) -> float:
    if not segments:
        return 0.0
    last = segments[-1]
    return round(last.start + last.duration, 3)


def transcribe(
    video_id: str | None = None,
    url: str | None = None,
    languages: list[str] | None = None,
    force_audio: bool = False,
) -> TranscribeResponse:
    """Run the fallback chain and return a normalised transcript."""
    settings = get_settings()
    vid = extract_video_id(video_id, url)
    langs = languages or settings.default_languages

    # Tier 1: captions.
    if not force_audio:
        try:
            language, segments = captions.fetch_captions(vid, langs)
            return TranscribeResponse(
                video_id=vid,
                language=language,
                source=TranscriptSource.captions,
                segments=segments,
                text=_join_text(segments),
                duration_s=_total_duration(segments),
            )
        except captions.NoCaptionsError:
            pass  # fall through to audio tier

    # Tier 2: audio download + the configured Whisper/STT backend.
    backend = _stt_backend()
    wav_path = audio.download_audio(vid, settings.work_dir)
    try:
        chunks = audio.split_audio(wav_path)
        language, segments = backend.transcribe_chunks(chunks, language=langs[0] if langs else None)
    finally:
        # Always reclaim disk, even if STT raises.
        audio.cleanup_video(settings.work_dir, vid)
    return TranscribeResponse(
        video_id=vid,
        language=language,
        source=getattr(backend, "SOURCE", TranscriptSource.whisper_local),
        segments=segments,
        text=_join_text(segments),
        duration_s=_total_duration(segments),
    )
