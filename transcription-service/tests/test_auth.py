"""Tests for hardening: optional API-key auth and the batch size cap."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.models import Segment, TranscribeResponse, TranscriptSource

client = TestClient(main.app)


def _resp() -> TranscribeResponse:
    return TranscribeResponse(
        video_id="dQw4w9WgXcQ",
        language="en",
        source=TranscriptSource.captions,
        segments=[Segment(start=0.0, duration=1.0, text="hi")],
        text="hi",
        duration_s=1.0,
    )


def test_no_auth_required_when_key_unset(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(api_key=""))
    monkeypatch.setattr(main, "transcribe", lambda **kw: _resp())
    resp = client.post("/transcribe", json={"video_id": "dQw4w9WgXcQ"})
    assert resp.status_code == 200


def test_missing_key_rejected_when_required(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(api_key="secret"))
    resp = client.post("/transcribe", json={"video_id": "dQw4w9WgXcQ"})
    assert resp.status_code == 401


def test_correct_key_accepted(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(api_key="secret"))
    monkeypatch.setattr(main, "transcribe", lambda **kw: _resp())
    resp = client.post(
        "/transcribe",
        json={"video_id": "dQw4w9WgXcQ"},
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 200


def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(api_key="secret"))
    resp = client.post(
        "/transcribe",
        json={"video_id": "dQw4w9WgXcQ"},
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401


def test_batch_rejects_oversized_request(monkeypatch):
    monkeypatch.setattr(
        main, "get_settings", lambda: SimpleNamespace(api_key="", batch_max_items=2)
    )
    resp = client.post(
        "/transcribe/batch",
        json={"items": [{"video_id": f"vid{i:08d}"} for i in range(3)]},
    )
    assert resp.status_code == 400
    assert "batch too large" in resp.json()["detail"]
