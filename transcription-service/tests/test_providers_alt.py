"""ElevenLabs and MLX backend tests — external calls mocked, no network/HW."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.transcribe as orchestrator
from app.models import TranscriptSource
from app.providers import elevenlabs, whisper_mlx
from app.providers.audio import AudioChunk


# --------------------------------------------------------------------------- #
# Backend dispatch
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "backend,module,source",
    [
        ("local", "whisper_local", TranscriptSource.whisper_local),
        ("cloud", "whisper_cloud", TranscriptSource.whisper_cloud),
        ("elevenlabs", "elevenlabs", TranscriptSource.elevenlabs),
        ("mlx", "whisper_mlx", TranscriptSource.mlx),
        ("unknown", "whisper_local", TranscriptSource.whisper_local),  # safe default
    ],
)
def test_backend_selection_and_source(monkeypatch, backend, module, source):
    monkeypatch.setattr(orchestrator, "get_settings", lambda: SimpleNamespace(stt_backend=backend))
    selected = orchestrator._stt_backend()
    assert selected.__name__.endswith(module)
    assert getattr(selected, "SOURCE", TranscriptSource.whisper_local) == source


# --------------------------------------------------------------------------- #
# ElevenLabs Scribe
# --------------------------------------------------------------------------- #
def _el_settings(api_key: str = "k"):
    return SimpleNamespace(
        elevenlabs_api_key=api_key,
        elevenlabs_base_url="https://api.elevenlabs.io/v1",
        elevenlabs_model="scribe_v1",
    )


def test_elevenlabs_requires_key(monkeypatch):
    monkeypatch.setattr(elevenlabs, "get_settings", lambda: _el_settings(""))
    with pytest.raises(elevenlabs.ElevenLabsError):
        elevenlabs.transcribe_chunks([], language="en")


def test_elevenlabs_stitches_word_timings(monkeypatch, tmp_path):
    monkeypatch.setattr(elevenlabs, "get_settings", lambda: _el_settings())
    c0 = tmp_path / "c0.wav"
    c0.write_bytes(b"x")
    chunks = [AudioChunk(path=str(c0), offset_s=900.0)]

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "language_code": "zh",
                "text": "hello world",
                "words": [
                    {"text": "hello", "start": 0.0, "end": 0.5, "type": "word"},
                    {"text": " ", "start": 0.5, "end": 0.6, "type": "spacing"},
                    {"text": "world", "start": 0.6, "end": 1.0, "type": "word"},
                ],
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

    language, segments = elevenlabs.transcribe_chunks(chunks, language="zh")
    assert language == "zh"
    # Spacing token dropped; two words shifted by the 900s chunk offset.
    assert [s.text for s in segments] == ["hello", "world"]
    assert segments[0].start == 900.0
    assert segments[1].start == 900.6


def test_elevenlabs_falls_back_to_whole_text(monkeypatch, tmp_path):
    monkeypatch.setattr(elevenlabs, "get_settings", lambda: _el_settings())
    c0 = tmp_path / "c0.wav"
    c0.write_bytes(b"x")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"language_code": "en", "text": "no word timings", "words": []}

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

    _, segments = elevenlabs.transcribe_chunks(
        [AudioChunk(path=str(c0), offset_s=0.0)], language="en"
    )
    assert len(segments) == 1
    assert segments[0].text == "no word timings"


# --------------------------------------------------------------------------- #
# Apple MLX
# --------------------------------------------------------------------------- #
def test_mlx_raises_clear_error_when_unavailable(monkeypatch):
    # Simulate the package being absent (the case on non-Apple-Silicon / CI).
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "mlx_whisper":
            raise ImportError("no mlx on this platform")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(whisper_mlx.MlxNotAvailableError):
        whisper_mlx.transcribe_chunks([], language="en")
