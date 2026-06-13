"""Opt-in integration tests that hit real external services.

Skipped by default so CI and offline runs stay hermetic. Enable explicitly:

    RUN_INTEGRATION=1 pytest tests/test_integration.py

Note: from datacenter/CI IPs YouTube usually returns 403/410 (TranscriptBlocked).
That is itself a meaningful signal — these tests document how to validate the
live path once a residential proxy (TRANSCRIBER_WEBSHARE_PROXY_*) is configured.
"""

from __future__ import annotations

import os

import pytest

from app.providers import captions

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="set RUN_INTEGRATION=1 to run network integration tests",
)


def test_real_captions_fetch():
    # "jNQXAC9IVRw" (Me at the zoo) is the oldest public video with captions.
    try:
        language, segments = captions.fetch_captions("jNQXAC9IVRw", ["en"])
    except captions.TranscriptBlockedError as exc:
        pytest.skip(f"YouTube blocked this IP (expected without a proxy): {exc}")
    assert language
    assert len(segments) > 0
    assert any(s.text.strip() for s in segments)
