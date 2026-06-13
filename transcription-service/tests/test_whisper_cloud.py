"""Cloud STT backend tests — httpx mocked, no network or key required."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers import whisper_cloud
from app.providers.audio import AudioChunk


def _settings(api_key: str = "k"):
    return SimpleNamespace(
        cloud_stt_api_key=api_key,
        cloud_stt_base_url="https://api.example/openai/v1",
        cloud_stt_model="whisper-large-v3",
    )


def test_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(whisper_cloud, "get_settings", lambda: _settings(api_key=""))
    with pytest.raises(whisper_cloud.CloudSTTError):
        whisper_cloud.transcribe_chunks([], language="en")


def test_stitches_segments_onto_global_timeline(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper_cloud, "get_settings", lambda: _settings())

    # Two chunks; the second starts 900s into the audio.
    c0 = tmp_path / "c0.wav"
    c1 = tmp_path / "c1.wav"
    c0.write_bytes(b"0")
    c1.write_bytes(b"1")
    chunks = [
        AudioChunk(path=str(c0), offset_s=0.0),
        AudioChunk(path=str(c1), offset_s=900.0),
    ]

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "language": "zh",
                "segments": [{"start": 1.0, "end": 3.0, "text": " hello "}],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)

    language, segments = whisper_cloud.transcribe_chunks(chunks, language="zh")

    assert language == "zh"
    assert len(segments) == 2
    # First chunk segment keeps its local offset, second is shifted by 900s.
    assert segments[0].start == 1.0
    assert segments[1].start == 901.0
    assert segments[0].duration == 2.0
    assert segments[0].text == "hello"


def test_raises_on_non_200(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper_cloud, "get_settings", lambda: _settings())
    chunk_path = tmp_path / "c.wav"
    chunk_path.write_bytes(b"x")

    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)

    with pytest.raises(whisper_cloud.CloudSTTError):
        whisper_cloud.transcribe_chunks(
            [AudioChunk(path=str(chunk_path), offset_s=0.0)], language="en"
        )
