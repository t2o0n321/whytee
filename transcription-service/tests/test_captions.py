"""Captions provider: error-mapping tests (no network)."""

from __future__ import annotations

import pytest

import app.transcribe as orchestrator
from app.providers import captions


def test_blocked_errors_are_resolved():
    # In the pinned 1.x line these classes exist; the helper must find at least
    # one so 403/IP-block responses get the actionable error instead of a 502.
    assert captions._blocked_errors(), "expected youtube-transcript-api block classes"


def test_library_block_maps_to_transcript_blocked_error(monkeypatch):
    import youtube_transcript_api as yta
    from youtube_transcript_api import _errors as e

    class FakeApi:
        def __init__(self, *a, **k):
            pass

        def list(self, video_id):
            raise e.RequestBlocked(video_id)

    monkeypatch.setattr(yta, "YouTubeTranscriptApi", FakeApi)

    with pytest.raises(captions.TranscriptBlockedError) as excinfo:
        captions.fetch_captions("dQw4w9WgXcQ", ["en"])
    # The message must point operators at the proxy mitigation.
    assert "proxy" in str(excinfo.value).lower()


def test_orchestrator_propagates_block_instead_of_falling_to_audio(monkeypatch):
    def raise_blocked(video_id, languages):
        raise captions.TranscriptBlockedError("blocked")

    monkeypatch.setattr(captions, "fetch_captions", raise_blocked)
    # If captions are blocked, audio (same IP) would also be blocked — the
    # orchestrator must surface the block, not silently try the audio tier.
    monkeypatch.setattr(
        orchestrator.audio,
        "download_audio",
        lambda *a, **k: pytest.fail("audio tier must not run on a block"),
    )

    with pytest.raises(captions.TranscriptBlockedError):
        orchestrator.transcribe(video_id="dQw4w9WgXcQ")
