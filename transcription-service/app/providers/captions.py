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


class TranscriptBlockedError(Exception):
    """Raised when YouTube blocks the request (403 / IP block / 410 Gone).

    This is the dominant real-world failure mode from datacenter IPs. The
    message points at the documented mitigation: configure a residential proxy
    (``TRANSCRIBER_WEBSHARE_PROXY_*``) and increase the n8n Wait delay.
    """


_BLOCKED_HINT = (
    "YouTube blocked the request ({exc}). Datacenter/server IPs are frequently "
    "rate-limited (403/410). Configure a residential proxy via "
    "TRANSCRIBER_WEBSHARE_PROXY_USERNAME/PASSWORD and increase the n8n Wait delay."
)


def _blocked_errors() -> tuple[type[Exception], ...]:
    """Resolve the library's block/throttle exception classes defensively.

    Names differ across youtube-transcript-api versions, so import what exists
    and fall back to an empty tuple (no special-casing) if unavailable.
    """
    classes: list[type[Exception]] = []
    try:
        from youtube_transcript_api import _errors as e

        for name in ("RequestBlocked", "IpBlocked", "YouTubeRequestFailed"):
            cls = getattr(e, name, None)
            if isinstance(cls, type) and issubclass(cls, Exception):
                classes.append(cls)
    except Exception:  # noqa: BLE001 - missing/renamed module: degrade gracefully
        pass
    return tuple(classes)


def fetch_captions(video_id: str, languages: list[str]) -> tuple[str, list[Segment]]:
    """Return ``(language_code, segments)`` for the best matching caption track.

    Resolution order:
      1. A manually-created or auto-generated track in one of ``languages``.
      2. Any available track auto-translated into the first requested language.

    Raises :class:`NoCaptionsError` if the video simply has no usable captions,
    or :class:`TranscriptBlockedError` if YouTube rejected the request (so the
    caller can surface actionable proxy/rate-limit guidance instead of a vague
    failure).
    """
    # Imported lazily so unit tests can patch this module without the dependency
    # and so the service boots in environments where the package is absent.
    from youtube_transcript_api import (
        NoTranscriptFound,
        TranscriptsDisabled,
        YouTubeTranscriptApi,
    )

    blocked = _blocked_errors()
    proxy_config = get_youtube_transcript_proxy()
    api = YouTubeTranscriptApi(proxy_config=proxy_config)

    try:
        transcript_list = api.list(video_id)
        transcript = _select_transcript(transcript_list, languages)
        if transcript is None:
            raise NoCaptionsError(f"no caption track matched {languages}")
        fetched = transcript.fetch()
    except (TranscriptsDisabled, NoTranscriptFound) as exc:
        raise NoCaptionsError(str(exc)) from exc
    except blocked as exc:  # type: ignore[misc]  # empty tuple => never matches
        raise TranscriptBlockedError(_BLOCKED_HINT.format(exc=type(exc).__name__)) from exc

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
