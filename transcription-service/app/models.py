"""Pydantic request/response schemas — the contract the n8n HTTP Request node
consumes. Field names stay English by convention; see docs/api.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TranscriptSource(str, Enum):
    """Which tier / backend of the fallback chain produced the transcript."""

    captions = "captions"  # tier 1: youtube-transcript-api
    whisper_local = "whisper_local"  # tier 2: yt-dlp + faster-whisper
    whisper_cloud = "whisper_cloud"  # tier 2: OpenAI-compatible cloud Whisper
    elevenlabs = "elevenlabs"  # tier 2: ElevenLabs Scribe
    mlx = "mlx"  # tier 2: Apple MLX Whisper


class TranscribeRequest(BaseModel):
    """Either `video_id` or `url` must be supplied."""

    video_id: str | None = Field(default=None, description="11-char YouTube id")
    url: str | None = Field(default=None, description="Full YouTube watch URL")
    languages: list[str] | None = Field(
        default=None,
        description="Language priority array; falls back to server default.",
    )
    force_audio: bool = Field(
        default=False,
        description="Skip captions and go straight to audio + Whisper.",
    )

    @model_validator(mode="after")
    def _require_identifier(self) -> TranscribeRequest:
        if not self.video_id and not self.url:
            raise ValueError("one of `video_id` or `url` is required")
        return self


class Segment(BaseModel):
    """A single time-indexed transcript line."""

    start: float = Field(description="start offset in seconds")
    duration: float = Field(description="segment duration in seconds")
    text: str


class TranscribeResponse(BaseModel):
    video_id: str
    language: str
    source: TranscriptSource
    segments: list[Segment]
    text: str
    duration_s: float = Field(description="total covered duration in seconds")


class BatchTranscribeRequest(BaseModel):
    items: list[TranscribeRequest]


class BatchTranscribeResponse(BaseModel):
    results: list[TranscribeResponse]
    errors: list[dict] = Field(default_factory=list)
