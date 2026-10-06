"""Raw librosa feature extraction. Returns plain numeric dict, no labels."""

from __future__ import annotations

import numpy as np


def _safe_mean(x: np.ndarray) -> float:
    """NaN-safe mean that returns 0.0 for empty arrays."""
    if x.size == 0:
        return 0.0
    value = float(np.nanmean(x))
    return 0.0 if np.isnan(value) else value


def _safe_std(x: np.ndarray) -> float:
    """NaN-safe std that returns 0.0 for empty arrays."""
    if x.size == 0:
        return 0.0
    value = float(np.nanstd(x))
    return 0.0 if np.isnan(value) else value


def extract_features(y: np.ndarray, sr: int) -> dict[str, float | None]:
    """Extract spectral and prosodic features from a waveform.

    Returns a flat dict of numeric values. No labels, no severity, no verdicts.
    """
    import librosa

    y = np.asarray(y, dtype=np.float32).flatten()
    if y.size < sr // 10:
        pad = np.zeros(sr // 4, dtype=np.float32)
        y = np.concatenate([y, pad])

    n_fft = 512
    hop = 160
    stft = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=n_fft, hop_length=hop)
    zcr = librosa.feature.zero_crossing_rate(y, hop_length=hop)
    rms = librosa.feature.rms(y=y, hop_length=hop)
    flux = (
        np.sqrt(np.mean(np.diff(stft, axis=1) ** 2, axis=0))
        if stft.shape[1] > 1
        else np.array([0.0])
    )

    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=80, n_fft=n_fft, hop_length=hop)
    log_mel = librosa.power_to_db(mel, ref=np.max)

    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        f0_voiced = f0[np.isfinite(f0)]
        f0_mean = _safe_mean(f0_voiced)
        f0_std = _safe_std(f0_voiced)
        voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0
    except Exception:
        f0_mean, f0_std, voiced_ratio = 0.0, 0.0, 0.0

    return {
        "f0_mean_hz": round(f0_mean, 2),
        "f0_std_hz": round(f0_std, 2),
        "voiced_ratio": round(voiced_ratio, 3),
        "spectral_centroid_hz": round(_safe_mean(centroid), 1),
        "spectral_rolloff_hz": round(_safe_mean(rolloff), 1),
        "spectral_flux": round(_safe_mean(flux), 4),
        "zcr": round(_safe_mean(zcr), 4),
        "rms": round(_safe_mean(rms), 5),
        "log_mel_mean": round(_safe_mean(log_mel), 2),
        "log_mel_std": round(_safe_std(log_mel), 2),
    }
