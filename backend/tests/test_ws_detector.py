"""Test WebSocket with a stub detector (test-only, not in app/)."""

from __future__ import annotations

import json

import numpy as np
from fastapi.testclient import TestClient

from app.detectors import registry
from app.main import app

SAMPLE_RATE = 16000
START_MSG = json.dumps({
    "type": "start",
    "sample_rate": 16000,
    "channels": 1,
    "encoding": "pcm_s16le",
    "mode": "single",
})


class _StubDetector:
    """TEST-ONLY detector that returns a constant probability."""

    @property
    def name(self) -> str:
        return "stub-test-detector"

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def window_seconds(self) -> float:
        return 5.0

    def load(self) -> None:
        pass

    def predict(self, waveform: np.ndarray) -> float:
        return 0.5


def _pcm_silence(seconds: float) -> bytes:
    """Generate silent PCM frames."""
    n_samples = int(SAMPLE_RATE * seconds)
    return b"\x00\x00" * n_samples


def test_ws_with_stub_detector():
    """Register a stub detector, stream audio, verify results carry ai_probability=0.5."""
    detector = _StubDetector()
    registry.register(detector)

    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready"
            assert ready["detector"] == "stub-test-detector"

            messages: list[dict] = []
            received = 0.0
            last_result = 0.0
            for _ in range(12):
                ws.send_bytes(_pcm_silence(0.5))
                received += 0.5
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if received >= 5.0 and received - last_result >= 1.0:
                    result_msg = json.loads(ws.receive_text())
                    messages.append(result_msg)
                    last_result = received

            ws.send_text(json.dumps({"type": "stop"}))

        results = [m for m in messages if m["type"] == "result"]
        assert len(results) >= 1
        for r in results:
            assert r["ai_probability"] == 0.5
            assert r["latency_ms"] >= 0
            assert r["detector"] == "stub-test-detector"
    finally:
        registry.unregister("stub-test-detector")
