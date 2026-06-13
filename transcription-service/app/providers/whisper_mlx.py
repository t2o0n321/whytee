"""Tier 2 (alternative) — Apple MLX Whisper.

High-throughput local transcription on Apple Silicon via the optional
``mlx-whisper`` package. Exposes the same ``transcribe_chunks`` interface as the
other tier-2 providers. The dependency is intentionally NOT a hard requirement
(it only installs/runs on Apple Silicon); selecting this backend without it
installed raises a clear :class:`MlxNotAvailableError`.
"""

from __future__ import annotations

from app.config import get_settings
from app.models import Segment, TranscriptSource
from app.providers.audio import AudioChunk

SOURCE = TranscriptSource.mlx


class MlxNotAvailableError(Exception):
    """Raised when stt_backend='mlx' but the mlx-whisper package is unavailable."""


def transcribe_chunks(
    chunks: list[AudioChunk], language: str | None = None
) -> tuple[str, list[Segment]]:
    """Transcribe ordered chunks with MLX Whisper, stitching global offsets."""
    try:
        import mlx_whisper  # type: ignore
    except ImportError as exc:  # pragma: no cover - platform-specific dependency
        raise MlxNotAvailableError(
            "stt_backend='mlx' requires the optional 'mlx-whisper' package "
            "(Apple Silicon only). Install it or use stt_backend=local/cloud."
        ) from exc

    settings = get_settings()
    all_segments: list[Segment] = []
    detected_language = language or "unknown"

    for chunk in chunks:
        result = mlx_whisper.transcribe(
            chunk.path,
            path_or_hf_repo=settings.mlx_model,
            language=language,
        )
        detected_language = result.get("language", detected_language)
        for seg in result.get("segments", []):
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
