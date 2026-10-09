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


import pytest
from app.core.jobs import job_manager

@pytest.fixture(autouse=True)
def reset_job_manager():
    with job_manager.lock:
        job_manager.jobs.clear()
        job_manager.current_job_id = None
        job_manager.worker_thread = None

def test_analyze_sine(client):
    """A valid 1-second 440 Hz WAV returns a job."""
    wav_data = _make_wav(440.0, 1.0)
    resp = client.post("/api/v1/analyze", files={"file": ("test.wav", wav_data, "audio/wav")})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["duration_seconds"] == 1.0
    assert data["total_windows"] == 1
    
    # poll job
    import time
    for _ in range(20):
        res = client.get(f"/api/v1/jobs/{data['job_id']}").json()
        if res["status"] in ["done", "error"]:
            break
        time.sleep(0.1)
    
    assert res["status"] == "done"
    assert len(res["results"]) == 1
    assert res["results"][0]["t"] == 1.0
    
def test_analyze_empty(client):
    """An empty file returns 400."""
    resp = client.post("/api/v1/analyze", files={"file": ("empty.wav", b"", "audio/wav")})
    assert resp.status_code == 400

def test_analyze_429(client):
    """A second request while one runs returns 429."""
    wav_data = _make_wav(440.0, 5.0)
    resp1 = client.post("/api/v1/analyze", files={"file": ("test1.wav", wav_data, "audio/wav")})
    assert resp1.status_code == 200
    
    resp2 = client.post("/api/v1/analyze", files={"file": ("test2.wav", wav_data, "audio/wav")})
    assert resp2.status_code == 429
    
    # wait for first to finish
    import time
    for _ in range(50):
        res = client.get(f"/api/v1/jobs/{resp1.json()['job_id']}").json()
        if res["status"] in ["done", "error"]:
            break
        time.sleep(0.1)

import os
import pytest

@pytest.mark.skipif(not os.path.exists("data/human/h1.mp3"), reason="h1.mp3 missing")
def test_analyze_real_file(client):
    with open("data/human/h1.mp3", "rb") as f:
        resp = client.post("/api/v1/analyze", files={"file": ("h1.mp3", f.read(), "audio/mpeg")})
    
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    
    import time
    for _ in range(100):
        res = client.get(f"/api/v1/jobs/{job_id}").json()
        if res["status"] in ["done", "error"]:
            break
        time.sleep(0.1)
        
    assert res["status"] == "done"
    results = res["results"]
    assert len(results) > 10
    
    # Assert gapless seq
    seqs = [r["seq"] for r in results]
    assert seqs == list(range(1, len(results) + 1))
