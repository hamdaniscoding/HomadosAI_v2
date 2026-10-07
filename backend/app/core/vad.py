"""Silero VAD helper for speech detection and gating."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger("homados.vad")

_VAD_MODEL: Any = None


def get_vad_model() -> Any:
    """Lazy load and return the Silero VAD model."""
    global _VAD_MODEL
    if _VAD_MODEL is None:
        import silero_vad

        _VAD_MODEL = silero_vad.load_silero_vad()
    return _VAD_MODEL


def measure_speech_seconds(samples: np.ndarray, sample_rate: int = 16000) -> float:
    """Measure total speech duration in seconds for the given audio samples.

    Uses silero-vad to detect speech segments and returns the sum of speech durations.
    """
    if len(samples) == 0:
        return 0.0

    model = get_vad_model()
    import silero_vad

    tensor_audio = torch.from_numpy(samples)
    if tensor_audio.dtype != torch.float32:
        tensor_audio = tensor_audio.to(torch.float32)

    with torch.no_grad():
        timestamps = silero_vad.get_speech_timestamps(
            tensor_audio,
            model,
            sampling_rate=sample_rate,
            return_seconds=False,
        )

    total_speech_samples = sum(ts["end"] - ts["start"] for ts in timestamps)
    return float(total_speech_samples / sample_rate)
