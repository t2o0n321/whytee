"""Environment-driven configuration.

All knobs are read from environment variables (or a local .env file) so the
service stays stateless and 12-factor friendly. n8n owns scheduling and the
inter-request delay (Wait node); the values here are defaults the service
exposes for documentation and for standalone use.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRANSCRIBER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Language priority array tried in order before falling back to audio STT.
    default_languages: list[str] = ["zh-TW", "zh-Hant", "zh", "en"]

    # faster-whisper model size: tiny | base | small | medium | large-v3.
    # "base" keeps the scaffold runnable on CPU without a GPU.
    whisper_model: str = "base"
    whisper_device: str = "auto"  # auto | cpu | cuda
    whisper_compute_type: str = "int8"  # int8 keeps CPU memory low

    # Tier-2 STT backend. All backends expose the same ``transcribe_chunks``
    # interface so the orchestrator stays backend-agnostic:
    #   local       faster-whisper (default, no key, cross-platform)
    #   cloud       OpenAI-compatible Whisper endpoint (Groq / OpenRouter / OpenAI)
    #   elevenlabs  ElevenLabs Scribe speech-to-text
    #   mlx         Apple MLX Whisper (Apple Silicon only)
    stt_backend: str = "local"  # local | cloud | elevenlabs | mlx

    # Cloud Whisper (used when stt_backend="cloud"). OpenAI-compatible
    # /audio/transcriptions endpoint. Empty api key disables the cloud backend.
    cloud_stt_base_url: str = "https://api.groq.com/openai/v1"
    cloud_stt_model: str = "whisper-large-v3"
    cloud_stt_api_key: str = ""

    # ElevenLabs Scribe (used when stt_backend="elevenlabs").
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_model: str = "scribe_v1"
    elevenlabs_api_key: str = ""

    # Apple MLX Whisper (used when stt_backend="mlx"). Requires the optional
    # `mlx-whisper` package on Apple Silicon; the repo string names the model.
    mlx_model: str = "mlx-community/whisper-large-v3-mlx"

    # Audio handling: chunk long audio below the typical 25MB / 15-min STT limit.
    audio_chunk_seconds: int = 900  # 15 minutes

    # Politeness delay between channel requests (enforced by n8n Wait node).
    # Mirrors YTScribe's default 60s cooldown.
    request_delay_seconds: int = 60

    # Optional Webshare residential proxy (see proxy.py). Empty disables proxying.
    webshare_proxy_username: str = ""
    webshare_proxy_password: str = ""

    # Working directory for downloaded audio chunks.
    work_dir: str = "/tmp/transcriber"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
