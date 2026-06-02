"""FastAPI app exposing the transcription microservice.

These endpoints are consumed by n8n's HTTP Request node (see docs/workflows.md).
The service is stateless; rate-limiting / scheduling is owned by n8n.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from app import __version__
from app.config import get_settings
from app.models import (
    BatchTranscribeRequest,
    BatchTranscribeResponse,
    TranscribeRequest,
    TranscribeResponse,
)
from app.transcribe import transcribe

logger = logging.getLogger("transcriber")

app = FastAPI(
    title="YouTube Transcription Service",
    version=__version__,
    summary="Tiered-fallback transcription (captions -> local Whisper) for n8n.",
)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "default_languages": settings.default_languages,
        "whisper_model": settings.whisper_model,
    }


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe_endpoint(req: TranscribeRequest) -> TranscribeResponse:
    try:
        return transcribe(
            video_id=req.video_id,
            url=req.url,
            languages=req.languages,
            force_audio=req.force_audio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("transcription failed")
        raise HTTPException(status_code=502, detail=f"transcription failed: {exc}") from exc


@app.post("/transcribe/batch", response_model=BatchTranscribeResponse)
def transcribe_batch_endpoint(req: BatchTranscribeRequest) -> BatchTranscribeResponse:
    """Sequential batch helper for the historical-backfill workflow.

    n8n is expected to enforce the inter-request delay; this endpoint simply
    iterates and collects per-item errors rather than failing the whole batch.
    """
    results: list[TranscribeResponse] = []
    errors: list[dict] = []
    for item in req.items:
        try:
            results.append(
                transcribe(
                    video_id=item.video_id,
                    url=item.url,
                    languages=item.languages,
                    force_audio=item.force_audio,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"request": item.model_dump(), "error": str(exc)})
    return BatchTranscribeResponse(results=results, errors=errors)
