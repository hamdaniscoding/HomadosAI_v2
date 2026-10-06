"""Tests for the rolling audio buffer."""

from __future__ import annotations

import numpy as np

from app.core.buffer import RollingBuffer


def test_buffer_latest_after_overflow():
    """latest(5) after appending 7 s returns exactly 5 s of samples."""
    sr = 16000
    buf = RollingBuffer(capacity_seconds=10.0, sample_rate=sr)
    samples_7s = np.zeros(7 * sr, dtype=np.float32)
    buf.append(samples_7s)
    result = buf.latest(5.0)
    assert len(result) == 5 * sr


def test_buffer_total_seconds():
    """total_seconds tracks all received audio."""
    sr = 16000
    buf = RollingBuffer(capacity_seconds=5.0, sample_rate=sr)
    buf.append(np.zeros(sr, dtype=np.float32))
    buf.append(np.zeros(sr, dtype=np.float32))
    assert abs(buf.total_seconds - 2.0) < 1e-6
