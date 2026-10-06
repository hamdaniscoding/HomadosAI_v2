"""Audio decoding and PCM conversion utilities."""

from __future__ import annotations

import io

import numpy as np

TARGET_SR = 16000


def decode_upload(data: bytes, filename: str) -> tuple[np.ndarray, float]:
    """Decode an uploaded audio file to float32 mono 16 kHz.

    Returns (waveform, duration_seconds). Raises ValueError on failure.
    """
    import librosa
    import soundfile as sf

    if not data:
        raise ValueError("Empty audio data")

    buf = io.BytesIO(data)
    try:
        y, sr = sf.read(buf, always_2d=False)
        y = np.asarray(y, dtype=np.float32)
        if y.ndim > 1:
            y = y.mean(axis=1)
    except Exception:
        buf.seek(0)
        try:
            y, sr = librosa.load(buf, sr=TARGET_SR, mono=True)
        except Exception as exc:
            raise ValueError(f"Cannot decode audio file '{filename}'") from exc
        y = np.asarray(y, dtype=np.float32)
        duration = float(len(y)) / TARGET_SR
        return y, duration

    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)

    duration = float(len(y)) / TARGET_SR
    return y, duration


def pcm16_to_float32(data: bytes) -> np.ndarray:
    """Convert raw little-endian signed 16-bit PCM bytes to float32 array.

    Raises ValueError if byte length is odd.
    """
    if len(data) % 2 != 0:
        raise ValueError("PCM data has odd byte length")
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    return samples
