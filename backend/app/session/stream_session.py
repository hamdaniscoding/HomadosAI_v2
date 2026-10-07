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
        self.seq: int = 0
        self.probabilities: list[float] = []
        self.last_valid_result_at: float | None = None
        
        # Diarization state
        from app.speaker.diarizer import OnlineDiarizer
        self.diarizer = OnlineDiarizer()
        self.speech_buffer = np.zeros(0, dtype=np.float32)
        self.segment_size_samples = int(self._sample_rate * 1.5)

    def ingest(self, pcm_bytes: bytes) -> np.ndarray:
        """Decode PCM bytes, append to buffer, and return the float32 samples."""
        from app.core.vad import get_vad_model
        import silero_vad
        import torch

        samples = pcm16_to_float32(pcm_bytes)
        self.buffer.append(samples)
        self.received_seconds += len(samples) / self._sample_rate
        
        # Extract speech parts using VAD
        if len(samples) > 0:
            model = get_vad_model()
            tensor_audio = torch.from_numpy(samples).to(torch.float32)
            with torch.no_grad():
                timestamps = silero_vad.get_speech_timestamps(
                    tensor_audio,
                    model,
                    sampling_rate=self._sample_rate,
                    return_seconds=False,
                )
            speech_chunks = [samples[ts["start"]:ts["end"]] for ts in timestamps]
            if speech_chunks:
                chunk_speech = sum(len(c) for c in speech_chunks)
                self.speech_seconds += chunk_speech / self._sample_rate
                self.speech_buffer = np.concatenate([self.speech_buffer] + speech_chunks)
                
                # Feed to diarizer in 1.5s segments
                while len(self.speech_buffer) >= self.segment_size_samples:
                    segment = self.speech_buffer[:self.segment_size_samples]
                    self.speech_buffer = self.speech_buffer[self.segment_size_samples:]
                    spk_id = self.diarizer.process_segment(segment)
                    if spk_id is not None:
                        self.diarizer.speakers[spk_id].append_audio(segment, self._sample_rate)

        return samples
