"""Tests for the WebSocket streaming endpoint."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

SAMPLE_RATE = 16000
START_MSG = json.dumps({
    "type": "start",
    "sample_rate": 16000,
    "channels": 1,
    "encoding": "pcm_s16le",
    "mode": "single",
})


def _pcm_silence(seconds: float) -> bytes:
    """Generate silent PCM frames."""
    n_samples = int(SAMPLE_RATE * seconds)
    return b"\x00\x00" * n_samples


def test_ws_flow():
    """Stream 3 s of silent PCM in 0.5 s frames -> expect ready + 6 status messages."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/stream") as ws:
        ws.send_text(START_MSG)
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"
        assert "session_id" in ready

        status_count = 0
        for _ in range(6):
            ws.send_bytes(_pcm_silence(0.5))
            msg = json.loads(ws.receive_text())
            if msg["type"] == "status":
                status_count += 1
                assert "received_seconds" in msg

        assert status_count == 6
        ws.send_text(json.dumps({"type": "stop"}))


def test_ws_result():
    """Stream 6 s -> at least one result with reason no_detector_loaded.

    Each 0.5 s frame triggers a status message. Additionally, once we have
    >= 5.0 s and the hop interval (1.0 s) has elapsed, a result message
    follows the status. We must read both messages on those frames.
    """
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/stream") as ws:
        ws.send_text(START_MSG)
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"

        messages: list[dict] = []
        received = 0.0
        last_result = 0.0
        for _ in range(12):
            ws.send_bytes(_pcm_silence(0.5))
            received += 0.5
            # Always get the status message
            msg = json.loads(ws.receive_text())
            messages.append(msg)
            # Check if a result message is also expected on this frame
            if received >= 5.0 and received - last_result >= 1.0:
                result_msg = json.loads(ws.receive_text())
                messages.append(result_msg)
                last_result = received

        ws.send_text(json.dumps({"type": "stop"}))

        results = [m for m in messages if m["type"] == "result"]
        assert len(results) >= 1
        r = results[0]
        assert r["reason"] == "no_detector_loaded"
        assert r["ai_probability"] is None


def test_ws_missing_start():
    """Sending binary first -> error code invalid_start."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/stream") as ws:
        ws.send_bytes(_pcm_silence(0.5))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["code"] == "invalid_start"


def test_ws_bad_format():
    """Wrong sample rate -> unsupported_format."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/stream") as ws:
        ws.send_text(json.dumps({
            "type": "start",
            "sample_rate": 44100,
            "channels": 1,
            "encoding": "pcm_s16le",
            "mode": "single",
        }))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["code"] == "unsupported_format"


def test_ws_odd_frame():
    """3-byte frame -> bad_frame."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/stream") as ws:
        ws.send_text(START_MSG)
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"
        ws.send_bytes(b"\x00\x00\x00")
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["code"] == "bad_frame"
