"""Tier 2 (alternative) — cloud speech-to-text via an OpenAI-compatible Whisper
endpoint (Groq / OpenRouter / OpenAI).

Documented in docs/api.md as a drop-in alternative to the local faster-whisper
backend: it removes the local compute requirement at the cost of a paid API key
and per-request upload. It exposes the exact same ``transcribe_chunks``
interface as ``whisper_local`` so ``app.transcribe`` can dispatch on
``settings.stt_backend`` without any other change.

Each audio chunk is POSTed to ``{base_url}/audio/transcriptions`` with
``response_format=verbose_json`` so per-segment timings come back; offsets are
stitched onto the global timeline using each chunk's ``offset_s`` exactly like
the local backend.
"""

from __future__ import annotations

from app.config import get_settings
from app.models import Segment
from app.providers.audio import AudioChunk


class CloudSTTError(Exception):
    """Raised when the cloud STT endpoint is misconfigured or returns an error."""


def transcribe_chunks(
    chunks: list[AudioChunk], language: str | None = None
) -> tuple[str, list[Segment]]:
    """Transcribe ordered chunks via the cloud endpoint and stitch segments.

    Returns ``(language, segments)``. Raises :class:`CloudSTTError` when no API
    key is configured.
    """
    # Imported lazily so the dependency stays optional and unit tests can patch
    # this module without httpx installed.
    import httpx

    settings = get_settings()
    if not settings.cloud_stt_api_key:
        raise CloudSTTError("TRANSCRIBER_CLOUD_STT_API_KEY is required when stt_backend='cloud'")

    url = f"{settings.cloud_stt_base_url.rstrip('/')}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.cloud_stt_api_key}"}

    all_segments: list[Segment] = []
    detected_language = language or "unknown"

    with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
        for chunk in chunks:
            data = {"model": settings.cloud_stt_model, "response_format": "verbose_json"}
            if language:
                data["language"] = language
            with open(chunk.path, "rb") as fh:
                resp = client.post(
                    url,
                    headers=headers,
                    data=data,
                    files={"file": (f"{chunk.offset_s}.wav", fh, "audio/wav")},
                )
            if resp.status_code != 200:
                raise CloudSTTError(f"cloud STT {resp.status_code}: {resp.text[:200]}")
            payload = resp.json()
            detected_language = payload.get("language", detected_language)
            for seg in payload.get("segments", []):
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start))
                all_segments.append(
                    Segment(
                        start=chunk.offset_s + start,
                        duration=max(0.0, end - start),
                        text=(seg.get("text") or "").strip(),
                    )
                )

    return detected_language, all_segments
