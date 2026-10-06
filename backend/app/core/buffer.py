"""Thread-safe rolling audio buffer."""

from __future__ import annotations

import threading

import numpy as np


class RollingBuffer:
    """Fixed-capacity circular buffer for float32 audio samples."""

    def __init__(self, capacity_seconds: float, sample_rate: int) -> None:
        self._capacity = int(capacity_seconds * sample_rate)
        self._sr = sample_rate
        self._buf = np.zeros(self._capacity, dtype=np.float32)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()

    def append(self, samples: np.ndarray) -> None:
        """Append float32 samples to the buffer."""
        samples = np.asarray(samples, dtype=np.float32).ravel()
        n = len(samples)
        with self._lock:
            if n >= self._capacity:
                self._buf[:] = samples[-self._capacity:]
                self._write_pos = 0
                self._total_written += n
            else:
                end = self._write_pos + n
                if end <= self._capacity:
                    self._buf[self._write_pos:end] = samples
                else:
                    first = self._capacity - self._write_pos
                    self._buf[self._write_pos:] = samples[:first]
                    self._buf[:n - first] = samples[first:]
                self._write_pos = end % self._capacity
                self._total_written += n

    def latest(self, seconds: float) -> np.ndarray:
        """Return the most recent `seconds` worth of samples."""
        n = min(int(seconds * self._sr), self._capacity)
        with self._lock:
            filled = min(self._total_written, self._capacity)
            n = min(n, filled)
            if n == 0:
                return np.array([], dtype=np.float32)
            start = (self._write_pos - n) % self._capacity
            if start + n <= self._capacity:
                return self._buf[start:start + n].copy()
            first = self._capacity - start
            return np.concatenate([
                self._buf[start:],
                self._buf[:n - first],
            ])

    @property
    def total_seconds(self) -> float:
        """Total seconds of audio received (may exceed buffer capacity)."""
        with self._lock:
            return self._total_written / self._sr
