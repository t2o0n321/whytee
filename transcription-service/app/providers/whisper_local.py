"""Tier 2 — local speech-to-text with faster-whisper.

Chosen over the PDF's MLX/cloud Whisper options because faster-whisper runs
cross-platform on CPU or GPU with no paid API key, so the scaffold is verifiable
without secrets. Cloud Whisper (Groq/OpenRouter) and Apple MLX are documented in
docs/api.md as drop-in alternative providers behind the same interface.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.models import Segment, TranscriptSource
from app.providers.audio import AudioChunk

SOURCE = TranscriptSource.whisper_local


@lru_cache
def _get_model():
    """Lazily load (and cache) the Whisper model."""
    from faster_whisper import WhisperModel

    settings = get_settings()
    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def transcribe_chunks(
    chunks: list[AudioChunk], language: str | None = None
) -> tuple[str, list[Segment]]:
    """Transcribe ordered chunks and stitch segments back onto the global
    timeline using each chunk's offset. Returns ``(language, segments)``.
    """
    model = _get_model()
    all_segments: list[Segment] = []
    detected_language = language or "unknown"

    for chunk in chunks:
        segments, info = model.transcribe(chunk.path, language=language)
        detected_language = getattr(info, "language", detected_language)
        for seg in segments:
            all_segments.append(
                Segment(
                    start=chunk.offset_s + seg.start,
                    duration=max(0.0, seg.end - seg.start),
                    text=seg.text.strip(),
                )
            )

    return detected_language, all_segments
