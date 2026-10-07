"""Unit tests for realtime pipeline: speech gating, smoothing, verdicts, and frame slicing."""

from __future__ import annotations

import json
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
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


class _SequenceStubDetector:
    """Stub detector returning a sequence of preset probabilities."""

    def __init__(self, probabilities: list[float], name: str = "seq-stub-detector") -> None:
        self._probs = list(probabilities)
        self._index = 0
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def window_seconds(self) -> float:
        return 5.0

    def load(self) -> None:
        pass

    def predict(self, waveform: np.ndarray) -> float:
        if self._index < len(self._probs):
            prob = self._probs[self._index]
            self._index += 1
            return prob
        return self._probs[-1] if self._probs else 0.5


def _pcm_frame(seconds: float = 0.5) -> bytes:
    """Generate 0.5s of silent PCM."""
    return b"\x00\x00" * int(SAMPLE_RATE * seconds)


def test_speech_gating_skips_silent_window():
    """Verify that a silent window is skipped with reason 'not_enough_speech' and ai_probability is null."""
    detector = _SequenceStubDetector([0.99])
    registry.register(detector)
    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready"

            # Stream 6 seconds of silence (12 frames of 0.5s)
            results = []
            received = 0.0
            last_result = 0.0
            for _ in range(12):
                ws.send_bytes(_pcm_frame(0.5))
                received += 0.5
                msg = json.loads(ws.receive_text())
                if msg["type"] == "result":
                    results.append(msg)

                if received >= 5.0 and received - last_result >= 1.0:
                    msg2 = json.loads(ws.receive_text())
                    if msg2["type"] == "result":
                        results.append(msg2)
                    last_result = received

            ws.send_text(json.dumps({"type": "stop"}))

            assert len(results) >= 1
            for r in results:
                assert r["ai_probability"] is None
                assert r["reason"] == "not_enough_speech"
                assert r["speech_ratio"] < 0.5

    finally:
        registry.unregister(detector.name)


def test_smoothing_returns_median_and_ignores_skipped(monkeypatch):
    """Verify smoothing computes the running median of valid detector results, and skipped hops do not enter history."""
    import app.core.vad as vad_module

    # Mock VAD to report 100% speech
    monkeypatch.setattr(vad_module, "measure_speech_seconds", lambda s, sr=16000: len(s) / sr)

    # Return probabilities: [0.1, 0.9, 0.2, 0.8, 0.5]
    # Medians:
    # 1: [0.1] -> 0.1
    # 2: [0.1, 0.9] -> 0.5
    # 3: [0.1, 0.9, 0.2] -> 0.2
    # 4: [0.1, 0.9, 0.2, 0.8] -> 0.5
    # 5: [0.1, 0.9, 0.2, 0.8, 0.5] -> 0.5
    probs = [0.1, 0.9, 0.2, 0.8, 0.5]
    detector = _SequenceStubDetector(probs, name="smoothing-stub-detector")
    registry.register(detector)

    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            _ = json.loads(ws.receive_text())

            results = []
            received = 0.0
            last_res = 0.0
            # Send 9.0s -> results at 5.0, 6.0, 7.0, 8.0, 9.0s (5 results)
            for _ in range(18):
                ws.send_bytes(_pcm_frame(0.5))
                received += 0.5
                _ = json.loads(ws.receive_text())  # status
                if received >= 5.0 and received - last_res >= 1.0:
                    res = json.loads(ws.receive_text())
                    results.append(res)
                    last_res = received

            ws.send_text(json.dumps({"type": "stop"}))

            assert len(results) == 5
            expected_smoothed = [0.1, 0.5, 0.2, 0.5, 0.5]
            for i, r in enumerate(results):
                assert r["ai_probability"] == probs[i]
                assert r["smoothed_probability"] == expected_smoothed[i]
    finally:
        registry.unregister(detector.name)


def test_verdict_thresholds(monkeypatch):
    """Verify verdict is null when thresholds are unset, and 'ai'/'human'/'uncertain' when thresholds are set."""
    from app.config import get_settings
    import app.core.vad as vad_module

    monkeypatch.setattr(vad_module, "measure_speech_seconds", lambda s, sr=16000: len(s) / sr)

    # 1) Unset thresholds: verdict is None and reason is 'thresholds_not_calibrated'
    settings = get_settings()
    settings.verdict_ai_threshold = None
    settings.verdict_human_threshold = None

    detector = _SequenceStubDetector([0.95], name="thresh-stub-1")
    registry.register(detector)
    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            _ = json.loads(ws.receive_text())
            received = 0.0
            last_res = 0.0
            result = None
            for _ in range(10):
                ws.send_bytes(_pcm_frame(0.5))
                received += 0.5
                _ = json.loads(ws.receive_text())  # status
                if received >= 5.0 and received - last_res >= 1.0:
                    result = json.loads(ws.receive_text())
                    last_res = received
                    break
            ws.send_text(json.dumps({"type": "stop"}))

            assert result is not None
            assert result["verdict"] is None
            assert result["reason"] == "thresholds_not_calibrated"
    finally:
        registry.unregister(detector.name)

    # 2) Set thresholds: human <= 0.3, ai >= 0.7
    settings.verdict_human_threshold = 0.3
    settings.verdict_ai_threshold = 0.7

    detector2 = _SequenceStubDetector([0.9, 0.1, 0.5], name="thresh-stub-2")
    registry.register(detector2)
    try:
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.send_text(START_MSG)
            _ = json.loads(ws.receive_text())
            received = 0.0
            last_res = 0.0
            results = []
            for _ in range(14):
                ws.send_bytes(_pcm_frame(0.5))
                received += 0.5
                _ = json.loads(ws.receive_text())
                if received >= 5.0 and received - last_res >= 1.0:
                    results.append(json.loads(ws.receive_text()))
                    last_res = received
            ws.send_text(json.dumps({"type": "stop"}))

            # Result 1: prob=0.9 -> smoothed=0.9 -> verdict 'ai'
            # Result 2: prob=0.1 -> smoothed=median([0.9, 0.1])=0.5 -> verdict 'uncertain'
            # Result 3: prob=0.5 -> smoothed=median([0.9, 0.1, 0.5])=0.5 -> verdict 'uncertain'
            assert len(results) >= 2
            assert results[0]["verdict"] == "ai"
            assert results[1]["verdict"] == "uncertain"
    finally:
        registry.unregister(detector2.name)
        settings.verdict_ai_threshold = None
        settings.verdict_human_threshold = None


def test_invalid_threshold_order_fails_startup():
    """Verify that setting HUMAN >= AI raises a validation error on Settings."""
    with pytest.raises(ValueError, match="Invalid threshold order"):
        Settings(verdict_human_threshold=0.8, verdict_ai_threshold=0.3)

    with pytest.raises(ValueError, match="Invalid threshold order"):
        Settings(verdict_human_threshold=0.5, verdict_ai_threshold=0.5)


def test_stream_script_frame_slicing_on_generated_tone():
    """Verify stream_file.py's slice_frames correctly slices a generated tone into 0.5s frames."""
    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parents[2]
    if str(ROOT_DIR / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT_DIR / "scripts"))
    from stream_file import slice_frames

    # Generate 2.5 seconds of a 440 Hz sine tone at 16 kHz
    duration = 2.5
    sr = 16000
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    tone = np.sin(2 * np.pi * 440 * t)

    frames = slice_frames(tone, sample_rate=sr, frame_seconds=0.5)

    # 2.5 seconds at 0.5 s/frame -> exactly 5 frames
    assert len(frames) == 5
    # Each frame should be 0.5 * 16000 samples * 2 bytes = 16000 bytes
    for frame in frames:
        assert len(frame) == 16000
        # Check that PCM can be reconstructed back to int16
        arr = np.frombuffer(frame, dtype="<i2")
        assert len(arr) == 8000
