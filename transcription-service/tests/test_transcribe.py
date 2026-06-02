"""Fallback-order tests with mocked providers — no network or model needed."""

from __future__ import annotations

import pytest

from app import transcribe as orchestrator
from app.models import Segment, TranscriptSource
from app.providers import captions


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_from_url(url, expected):
    assert orchestrator.extract_video_id(None, url) == expected


def test_extract_video_id_requires_identifier():
    with pytest.raises(ValueError):
        orchestrator.extract_video_id(None, None)


def test_captions_tier_is_used_when_available(monkeypatch):
    segs = [Segment(start=0.0, duration=2.0, text="hello"),
            Segment(start=2.0, duration=2.0, text="world")]

    def fake_fetch(video_id, languages):
        assert video_id == "vid00000001"
        return "en", segs

    monkeypatch.setattr(captions, "fetch_captions", fake_fetch)
    # If captions succeed, audio/whisper must never be called.
    monkeypatch.setattr(
        orchestrator.audio, "download_audio",
        lambda *a, **k: pytest.fail("audio tier should not run"),
    )

    resp = orchestrator.transcribe(video_id="vid00000001")
    assert resp.source == TranscriptSource.captions
    assert resp.language == "en"
    assert resp.text == "hello world"
    assert resp.duration_s == 4.0


def test_falls_back_to_audio_when_no_captions(monkeypatch):
    def raise_no_captions(video_id, languages):
        raise captions.NoCaptionsError("none")

    monkeypatch.setattr(captions, "fetch_captions", raise_no_captions)
    monkeypatch.setattr(
        orchestrator.audio, "download_audio", lambda vid, d: "/tmp/x.wav"
    )
    monkeypatch.setattr(
        orchestrator.audio, "split_audio", lambda p: ["chunk0"]
    )

    whisper_segs = [Segment(start=0.0, duration=3.0, text="from audio")]
    monkeypatch.setattr(
        orchestrator.whisper_local,
        "transcribe_chunks",
        lambda chunks, language=None: ("zh", whisper_segs),
    )

    resp = orchestrator.transcribe(video_id="vid00000002")
    assert resp.source == TranscriptSource.whisper_local
    assert resp.language == "zh"
    assert resp.text == "from audio"


def test_force_audio_skips_captions(monkeypatch):
    monkeypatch.setattr(
        captions, "fetch_captions",
        lambda *a, **k: pytest.fail("captions must be skipped"),
    )
    monkeypatch.setattr(
        orchestrator.audio, "download_audio", lambda vid, d: "/tmp/x.wav"
    )
    monkeypatch.setattr(orchestrator.audio, "split_audio", lambda p: ["c0"])
    monkeypatch.setattr(
        orchestrator.whisper_local,
        "transcribe_chunks",
        lambda chunks, language=None: ("en", [Segment(start=0, duration=1, text="x")]),
    )

    resp = orchestrator.transcribe(video_id="vid00000003", force_audio=True)
    assert resp.source == TranscriptSource.whisper_local
