# ---------------------------------------------------------------------------
# Multi-stage build for the tiered-fallback transcription microservice.
#   builder  installs the package + dependencies into an isolated virtualenv
#   runtime  slim image with only ffmpeg + the venv, running as a non-root user
# ---------------------------------------------------------------------------

FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build the dependency set into a self-contained venv we can copy wholesale.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# README is referenced by pyproject's `readme`, so it must be present to install.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

# ---------------------------------------------------------------------------

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TRANSCRIBER_WORK_DIR=/tmp/transcriber

# ffmpeg backs yt-dlp audio extraction and the chunk splitter (tier 2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/transcriber \
    && chown -R appuser:appuser /tmp/transcriber

# Copy the prebuilt virtualenv (includes the installed `app` package).
COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
USER appuser

EXPOSE 8000

# Container-level liveness check (compose adds its own as well).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
