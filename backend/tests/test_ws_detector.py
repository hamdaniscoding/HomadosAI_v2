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


def test_ws_with_stub_detector(monkeypatch):
    """Register a stub detector, stream audio, verify results carry ai_probability=0.5."""
    import app.core.vad as vad_module
    monkeypatch.setattr(vad_module, "measure_speech_seconds", lambda s, sr=16000: len(s) / sr)

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
            assert "seq" in r
            assert r["ai_probability"] == 0.5
            assert r["latency_ms"] >= 0
            assert r["detector"] == "stub-test-detector"
    finally:
        registry.unregister("stub-test-detector")


class _SlowStubDetector:
    """TEST-ONLY detector that simulates a slow 1.5 s inference."""

    @property
    def name(self) -> str:
        return "slow-stub-detector"

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def window_seconds(self) -> float:
        return 5.0

    def load(self) -> None:
        pass

    def predict(self, waveform: np.ndarray) -> float:
        import time
        time.sleep(1.5)
        return 0.88


def test_ws_with_slow_stub_detector(monkeypatch):
    """Verify (a) status messages continue arriving while detector runs;
    (b) while detector is busy, the next hop yields reason 'detector_busy'.
    """
    import app.core.vad as vad_module
    monkeypatch.setattr(vad_module, "measure_speech_seconds", lambda s, sr=16000: len(s) / sr)

    detector = _SlowStubDetector()
    registry.register(detector)

    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready"
            assert ready["detector"] == "slow-stub-detector"

            # 1) Stream first 4.5s -> 9 frames, expect 9 status messages, no result yet
            for _ in range(9):
                ws.send_bytes(_pcm_silence(0.5))
                msg = json.loads(ws.receive_text())
                assert msg["type"] == "status"

            # 2) Frame 10: reaches 5.0s -> triggers inference (takes 1.5s in background thread)
            ws.send_bytes(_pcm_silence(0.5))
            msg10 = json.loads(ws.receive_text())
            assert msg10["type"] == "status"
            assert msg10["received_seconds"] == 5.0

            # 3) Immediately send Frame 11 (5.5s): inference still running.
            # Expect status message at 5.5s without blocking!
            ws.send_bytes(_pcm_silence(0.5))
            msg11 = json.loads(ws.receive_text())
            assert msg11["type"] == "status"
            assert msg11["received_seconds"] == 5.5

            # 4) Immediately send Frame 12 (6.0s): next hop is due (received_seconds - last_result_at == 1.0s),
            # but inference is still running (only ~0.1s elapsed, need 1.5s).
            # Should receive status message AND a result message with detector_busy!
            ws.send_bytes(_pcm_silence(0.5))
            msg12_status = json.loads(ws.receive_text())
            assert msg12_status["type"] == "status"
            assert msg12_status["received_seconds"] == 6.0

            msg12_result = json.loads(ws.receive_text())
            assert msg12_result["type"] == "result"
            assert msg12_result["reason"] == "detector_busy"
            assert msg12_result["ai_probability"] is None
            assert msg12_result["detector"] == "slow-stub-detector"

            # Wait for original inference to complete
            import time
            time.sleep(1.6)

            # Collect completed result from Frame 10
            msg_completed = json.loads(ws.receive_text())
            assert msg_completed["type"] == "result"
            assert msg_completed["ai_probability"] == 0.88
            assert msg_completed["reason"] == "thresholds_not_calibrated"

            ws.send_text(json.dumps({"type": "stop"}))
    finally:
        registry.unregister("slow-stub-detector")

def test_ws_stop_scores_final_window(monkeypatch):
    """Verify that sending stop flushes the final partial window if received_seconds > 0."""
    import app.core.vad as vad_module
    monkeypatch.setattr(vad_module, "measure_speech_seconds", lambda s, sr=16000: len(s) / sr)

    detector = _StubDetector()
    registry.register(detector)

    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready"

            # Send 2.5s of audio (not enough to trigger the 5.0s window loop)
            for _ in range(5):
                ws.send_bytes(_pcm_silence(0.5))
            
            ws.send_text(json.dumps({"type": "stop"}))
            
            messages = []
            while True:
                try:
                    msg = ws.receive_json()
                    messages.append(msg)
                except Exception:
                    break
            
            final_result = next((m for m in messages if m.get("type") == "result"), None)
            assert final_result is not None
            assert final_result["ai_probability"] == 0.5
            assert final_result["t"] == 2.5

    finally:
        registry.unregister("stub-test-detector")
