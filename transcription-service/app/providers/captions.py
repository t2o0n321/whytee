"""Tier 1 — official / auto-generated captions via youtube-transcript-api.

Fast, cheap, no audio download. Honours a language priority array and falls
back to YouTube's auto-translate engine, exactly as the PDF describes for
``youtube-transcript-api``.
"""

from __future__ import annotations

from app.models import Segment
from app.proxy import get_youtube_transcript_proxy


class NoCaptionsError(Exception):
    """Raised when no caption track can be obtained for the video."""


def fetch_captions(video_id: str, languages: list[str]) -> tuple[str, list[Segment]]:
    """Return ``(language_code, segments)`` for the best matching caption track.

    Resolution order:
      1. A manually-created or auto-generated track in one of ``languages``.
      2. Any available track auto-translated into the first requested language.

    Raises :class:`NoCaptionsError` if nothing is available.
    """
    # Imported lazily so unit tests can patch this module without the dependency
    # and so the service boots in environments where the package is absent.
    from youtube_transcript_api import (
        NoTranscriptFound,
        TranscriptsDisabled,
        YouTubeTranscriptApi,
    )

    proxy_config = get_youtube_transcript_proxy()
    api = YouTubeTranscriptApi(proxy_config=proxy_config)

    try:
        transcript_list = api.list(video_id)
    except (TranscriptsDisabled, NoTranscriptFound) as exc:
        raise NoCaptionsError(str(exc)) from exc

    transcript = _select_transcript(transcript_list, languages)
    if transcript is None:
        raise NoCaptionsError(f"no caption track matched {languages}")

    fetched = transcript.fetch()
    segments = [Segment(start=s.start, duration=s.duration, text=s.text) for s in fetched]
    return transcript.language_code, segments


def _select_transcript(transcript_list, languages: list[str]):
    """Pick a directly-available track, else auto-translate the first track."""
    try:
        return transcript_list.find_transcript(languages)
    except Exception:  # noqa: BLE001 - library raises NoTranscriptFound subclasses
        pass

    # Fall back to translating whatever track exists into the top language.
    for transcript in transcript_list:
        if transcript.is_translatable and languages:
            try:
                return transcript.translate(languages[0])
            except Exception:  # noqa: BLE001
                continue
    return None
