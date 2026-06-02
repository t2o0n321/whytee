"""Webshare residential-proxy rotation hook.

The PDF calls out IP rate-limiting / 410 Gone as the main obstacle to large
channel back-fills, and recommends rotating residential proxies (e.g. Webshare).
This module is the single injectable point so the rest of the code stays
proxy-agnostic. With no credentials configured it returns ``None`` and the
service makes direct requests.
"""

from __future__ import annotations

from app.config import get_settings


def get_youtube_transcript_proxy():
    """Return a youtube-transcript-api proxy config, or None if disabled.

    Imported lazily so the package is optional at import time and the service
    boots even when youtube-transcript-api is unavailable in a dev shell.
    """
    settings = get_settings()
    if not (settings.webshare_proxy_username and settings.webshare_proxy_password):
        return None

    from youtube_transcript_api.proxies import WebshareProxyConfig

    return WebshareProxyConfig(
        proxy_username=settings.webshare_proxy_username,
        proxy_password=settings.webshare_proxy_password,
    )


def get_ytdlp_proxy_url() -> str | None:
    """Return a proxy URL suitable for yt-dlp's ``proxy`` option, or None."""
    settings = get_settings()
    if not (settings.webshare_proxy_username and settings.webshare_proxy_password):
        return None
    # Webshare rotating endpoint; the gateway handles per-request IP rotation.
    return (
        f"http://{settings.webshare_proxy_username}:"
        f"{settings.webshare_proxy_password}@p.webshare.io:80"
    )
