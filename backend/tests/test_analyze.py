"""Tests for POST /api/v1/analyze."""

from __future__ import annotations

import io
import struct
import wave

import numpy as np


def _make_wav(freq: float = 440.0, duration: float = 1.0, sr: int = 16000) -> bytes:
    """Generate a WAV file with a sine tone."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    samples = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_analyze_sine(client):
    """A valid 1-second 440 Hz WAV returns 200 with verdict null."""
    wav_data = _make_wav(440.0, 1.0)
    resp = client.post("/api/v1/analyze", files={"file": ("test.wav", wav_data, "audio/wav")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "test.wav"
    assert data["verdict"] is None
    assert data["reason"] == "no_detector_loaded"
    assert data["duration_seconds"] > 0
    assert data["sample_rate"] == 16000


def test_analyze_empty(client):
    """An empty file returns 400."""
    resp = client.post("/api/v1/analyze", files={"file": ("empty.wav", b"", "audio/wav")})
    assert resp.status_code == 400
