"""FastAPI endpoint tests via TestClient — no network, providers stubbed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Segment, TranscribeResponse, TranscriptSource

client = TestClient(main.app)


def _sample_response(vid: str = "dQw4w9WgXcQ") -> TranscribeResponse:
    return TranscribeResponse(
        video_id=vid,
        language="en",
        source=TranscriptSource.captions,
        segments=[Segment(start=0.0, duration=2.0, text="hi")],
        text="hi",
        duration_s=2.0,
    )


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "stt_backend" in body
    assert "X-Request-ID" in resp.headers


def test_ready_local_is_ready():
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True


def test_ready_cloud_without_key_is_503(monkeypatch):
    fake = SimpleNamespace(stt_backend="cloud", cloud_stt_api_key="")
    monkeypatch.setattr(main, "get_settings", lambda: fake)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["ready"] is False


def test_transcribe_success_echoes_request_id(monkeypatch):
    monkeypatch.setattr(main, "transcribe", lambda **kwargs: _sample_response())
    resp = client.post(
        "/transcribe",
        json={"video_id": "dQw4w9WgXcQ"},
        headers={"X-Request-ID": "test-rid-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "captions"
    assert resp.headers["X-Request-ID"] == "test-rid-123"


def test_transcribe_missing_identifier_is_422():
    # model_validator rejects a body with neither video_id nor url.
    resp = client.post("/transcribe", json={})
    assert resp.status_code == 422


def test_transcribe_value_error_is_400(monkeypatch):
    def boom(**kwargs):
        raise ValueError("bad id")

    monkeypatch.setattr(main, "transcribe", boom)
    resp = client.post("/transcribe", json={"video_id": "dQw4w9WgXcQ"})
    assert resp.status_code == 400
    assert "bad id" in resp.json()["detail"]


def test_transcribe_failure_is_502(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(main, "transcribe", boom)
    resp = client.post("/transcribe", json={"video_id": "dQw4w9WgXcQ"})
    assert resp.status_code == 502
    assert "provider down" in resp.json()["detail"]


def test_batch_collects_per_item_errors(monkeypatch):
    def transcribe(video_id=None, **kwargs):
        if video_id == "bad":
            raise RuntimeError("nope")
        return _sample_response(video_id)

    monkeypatch.setattr(main, "transcribe", transcribe)
    resp = client.post(
        "/transcribe/batch",
        json={"items": [{"video_id": "dQw4w9WgXcQ"}, {"video_id": "bad"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["error"] == "nope"


@pytest.fixture(autouse=True)
def _generated_request_id_when_header_absent():
    """A request id is always present on the response even without the header."""
    resp = client.get("/health")
    assert resp.headers["X-Request-ID"]
