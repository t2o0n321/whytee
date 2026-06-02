# Transcription Service / 逐字稿微服務

Tiered-fallback YouTube transcription microservice. See the project-level
`docs/api.md` (zh-TW) for the full REST contract and `docs/architecture.md` for
how it fits into the n8n / OpenRouter / Supabase / Telegram pipeline.

## Tiers

1. `captions` — `youtube-transcript-api` (official / auto captions, with
   language-priority and auto-translate fallback).
2. `whisper_local` — `yt-dlp` audio download + `ffmpeg` chunking + `faster-whisper`
   local STT, used when no captions exist or `force_audio=true`.

## Local development

```bash
cd transcription-service
pip install -e ".[dev]"   # needs ffmpeg on PATH for the audio tier
pytest                    # provider-mocked tests, no network/keys required
uvicorn app.main:app --reload
curl localhost:8000/health
```

Configuration is environment-driven via the `TRANSCRIBER_` prefix (see
`app/config.py`).
