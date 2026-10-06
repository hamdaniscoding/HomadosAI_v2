"""Detector protocol: the interface every AI-voice detector must implement."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Detector(Protocol):
    """Interface for an AI-voice probability detector."""

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        ...

    @property
    def sample_rate(self) -> int:
        """Expected sample rate in Hz."""
        ...

    @property
    def window_seconds(self) -> float:
        """Minimum input duration in seconds."""
        ...

    def load(self) -> None:
        """Load model weights. May raise on failure."""
        ...

    def predict(self, waveform: np.ndarray) -> float:
        """Return AI probability in [0, 1]. Raises on bad input length."""
        ...
