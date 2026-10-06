"""Tests for GET /api/v1/health."""

from __future__ import annotations


def test_health(client):
    """Health endpoint returns correct structure and types."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["app_version"], str)
    assert isinstance(data["python_version"], str)
    assert data["torch_version"] is None or isinstance(data["torch_version"], str)
    assert isinstance(data["device"], str)
    assert isinstance(data["detectors"], list)
    assert isinstance(data["ecapa"], dict)
    assert "loaded" in data["ecapa"]
    assert "load_error" in data["ecapa"]
    assert data["last_inference_ms"] is None or isinstance(data["last_inference_ms"], (int, float))
