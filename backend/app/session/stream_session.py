"""WebSocket streaming session state."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np

from app.config import get_settings
from app.core.audio import pcm16_to_float32
from app.core.buffer import RollingBuffer


class StreamSession:
    """Holds state for one WebSocket streaming session."""

    def __init__(self) -> None:
        settings = get_settings()
        self.session_id: str = str(uuid.uuid4())
        self.start_time: datetime = datetime.now(timezone.utc)
        self.buffer: RollingBuffer = RollingBuffer(
            capacity_seconds=settings.window_seconds * 2,
            sample_rate=settings.sample_rate,
        )
        self.received_seconds: float = 0.0
        self.speech_seconds: float = 0.0
        self._sample_rate: int = settings.sample_rate
        self.probabilities: list[float] = []
        self.last_valid_result_at: float | None = None

    def ingest(self, pcm_bytes: bytes) -> np.ndarray:
        """Decode PCM bytes, append to buffer, and return the float32 samples."""
        from app.core.vad import measure_speech_seconds

        samples = pcm16_to_float32(pcm_bytes)
        self.buffer.append(samples)
        self.received_seconds += len(samples) / self._sample_rate
        chunk_speech = measure_speech_seconds(samples, self._sample_rate)
        self.speech_seconds += chunk_speech
        return samples
