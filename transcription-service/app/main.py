"""FastAPI app exposing the transcription microservice.

These endpoints are consumed by n8n's HTTP Request node (see docs/workflows.md).
The service is stateless; rate-limiting / scheduling is owned by n8n.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.logging_config import configure_logging, request_id_var
from app.models import (
    BatchTranscribeRequest,
    BatchTranscribeResponse,
    TranscribeRequest,
    TranscribeResponse,
)
from app.transcribe import transcribe

configure_logging()
logger = logging.getLogger("transcriber")

app = FastAPI(
    title="YouTube Transcription Service",
    version=__version__,
    summary="Tiered-fallback transcription (captions -> Whisper) for n8n.",
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign/propagate a request id, log timing, and echo it back as a header."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %sms",
            request.method,
            request.url.path,
            round(elapsed_ms, 1),
        )
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/health")
def health() -> dict:
    """Liveness probe — the process is up and configuration loaded."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "default_languages": settings.default_languages,
        "whisper_model": settings.whisper_model,
        "stt_backend": settings.stt_backend,
    }


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness probe — checks the configured tier-2 backend can be used.

    For the cloud backend this means an API key is present; the local backend is
    always considered ready (the model loads lazily on first audio request).
    """
    settings = get_settings()
    ready = True
    detail = "ok"
    if settings.stt_backend == "cloud" and not settings.cloud_stt_api_key:
        ready = False
        detail = "stt_backend=cloud but TRANSCRIBER_CLOUD_STT_API_KEY is empty"
    body = {"ready": ready, "stt_backend": settings.stt_backend, "detail": detail}
    return JSONResponse(status_code=200 if ready else 503, content=body)


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
