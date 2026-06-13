"""Tier 2 (alternative) — ElevenLabs Scribe speech-to-text.

Documented in docs/api.md as a drop-in alternative backend (99+ languages,
strong accuracy in noisy audio). Exposes the same ``transcribe_chunks``
interface as the other tier-2 providers so ``app.transcribe`` dispatches on
``settings.stt_backend`` with no other change.

Each chunk is POSTed to ``{base_url}/speech-to-text``; the returned word-level
timestamps are turned into segments and shifted onto the global timeline using
each chunk's ``offset_s``.
"""

from __future__ import annotations

from app.config import get_settings
from app.models import Segment, TranscriptSource
from app.providers.audio import AudioChunk

SOURCE = TranscriptSource.elevenlabs


class ElevenLabsError(Exception):
    """Raised when ElevenLabs is misconfigured or returns an error."""


def _segments_from_words(words: list[dict], offset_s: float) -> list[Segment]:
    segments: list[Segment] = []
    for w in words:
        if w.get("type") not in (None, "word"):
            continue  # skip spacing/audio-event tokens
        text = (w.get("text") or "").strip()
        if not text:
            continue
        start = float(w.get("start", 0.0))
        end = float(w.get("end", start))
        segments.append(Segment(start=offset_s + start, duration=max(0.0, end - start), text=text))
    return segments


def transcribe_chunks(
    chunks: list[AudioChunk], language: str | None = None
) -> tuple[str, list[Segment]]:
    """Transcribe ordered chunks via ElevenLabs Scribe and stitch segments."""
    import httpx

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise ElevenLabsError(
            "TRANSCRIBER_ELEVENLABS_API_KEY is required when stt_backend='elevenlabs'"
        )

    url = f"{settings.elevenlabs_base_url.rstrip('/')}/speech-to-text"
    headers = {"xi-api-key": settings.elevenlabs_api_key}

    all_segments: list[Segment] = []
    detected_language = language or "unknown"

    with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
        for chunk in chunks:
            data = {"model_id": settings.elevenlabs_model}
            if language:
                data["language_code"] = language
            with open(chunk.path, "rb") as fh:
                resp = client.post(
                    url,
                    headers=headers,
                    data=data,
                    files={"file": (f"{chunk.offset_s}.wav", fh, "audio/wav")},
                )
            if resp.status_code != 200:
                raise ElevenLabsError(f"ElevenLabs {resp.status_code}: {resp.text[:200]}")
            payload = resp.json()
            detected_language = payload.get("language_code", detected_language)
            words = payload.get("words") or []
            chunk_segments = _segments_from_words(words, chunk.offset_s)
            if not chunk_segments and payload.get("text"):
                # No word timings returned: keep the whole-chunk text as one segment.
                chunk_segments = [
                    Segment(start=chunk.offset_s, duration=0.0, text=payload["text"].strip())
                ]
            all_segments.extend(chunk_segments)

    return detected_language, all_segments
