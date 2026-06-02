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
from app.providers import audio, captions, whisper_local

_VIDEO_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|youtu\.be/)([0-9A-Za-z_-]{11})"
)


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

    # Tier 2: audio download + local Whisper.
    wav_path = audio.download_audio(vid, settings.work_dir)
    chunks = audio.split_audio(wav_path)
    language, segments = whisper_local.transcribe_chunks(
        chunks, language=langs[0] if langs else None
    )
    return TranscribeResponse(
        video_id=vid,
        language=language,
        source=TranscriptSource.whisper_local,
        segments=segments,
        text=_join_text(segments),
        duration_s=_total_duration(segments),
    )
