"""Unit tests for score_folder evaluation functions (AUC, EER, and windowing).

NOTE: Tests run on purely synthetic numerical arrays with known scores.
No network calls and no audio files are loaded.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure scripts directory is available for importing score_folder functions
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from score_folder import (
    compute_eer,
    compute_roc_auc,
    slice_waveform_windows,
)


def test_roc_auc_perfect_separation():
    """Verify AUC is 1.0 when AI and human scores are completely separated."""
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_score = np.array([0.05, 0.12, 0.20, 0.85, 0.91, 0.99])
    auc = compute_roc_auc(y_true, y_score)
    assert auc == 1.0


def test_roc_auc_inverted_separation():
    """Verify AUC is 0.0 when predictions are completely inverted."""
    y_true = np.array([0, 0, 1, 1])
    y_score = np.array([0.9, 0.8, 0.2, 0.1])
    auc = compute_roc_auc(y_true, y_score)
    assert auc == 0.0


def test_roc_auc_tied_predictions():
    """Verify AUC handles ties correctly giving 0.5 for indistinguishable predictions."""
    y_true = np.array([0, 1, 0, 1])
    y_score = np.array([0.5, 0.5, 0.5, 0.5])
    auc = compute_roc_auc(y_true, y_score)
    assert auc == 0.5


def test_roc_auc_matches_sklearn():
    """Verify our pure-numpy AUC matches scikit-learn on a non-trivial random dataset."""
    from sklearn.metrics import roc_auc_score

    np.random.seed(42)
    y_true = np.random.randint(0, 2, size=100)
    y_score = np.random.rand(100)

    auc_custom = compute_roc_auc(y_true, y_score)
    auc_sk = roc_auc_score(y_true, y_score)
    assert abs(auc_custom - auc_sk) < 1e-9


def test_roc_auc_single_class_returns_nan():
    """Verify AUC returns NaN when only one class is present."""
    y_true = np.array([1, 1, 1])
    y_score = np.array([0.8, 0.9, 0.95])
    assert math.isnan(compute_roc_auc(y_true, y_score))


def test_eer_perfect_separation():
    """Verify EER is 0.0 when distributions do not overlap."""
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_score = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
    eer, threshold = compute_eer(y_true, y_score)
    assert eer == 0.0
    assert 0.3 <= threshold <= 0.7


def test_eer_overlapping_distributions():
    """Verify EER calculation on a symmetric overlapping distribution."""
    # Negatives: 0.1, 0.3, 0.5
    # Positives: 0.5, 0.7, 0.9
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_score = np.array([0.1, 0.3, 0.5, 0.5, 0.7, 0.9])
    eer, threshold = compute_eer(y_true, y_score)
    # Threshold at 0.5 gives FAR = 1/3, FRR = 0/3.
    # Crossing gives EER around ~16-33%.
    assert 0.0 <= eer <= 0.5
    assert 0.1 <= threshold <= 0.9


def test_eer_single_class_returns_nan():
    """Verify EER returns NaN when only one class is present."""
    y_true = np.array([0, 0, 0])
    y_score = np.array([0.1, 0.2, 0.3])
    eer, th = compute_eer(y_true, y_score)
    assert math.isnan(eer)
    assert math.isnan(th)


def test_slice_waveform_windows():
    """Verify non-overlapping 5-second windowing and skipping short remainders."""
    sr = 16000

    # 1. Exactly 5 seconds -> 1 window
    wave_5s = np.zeros(5 * sr, dtype=np.float32)
    windows_5s = slice_waveform_windows(wave_5s, sr=sr)
    assert len(windows_5s) == 1
    assert windows_5s[0][0] == 0.0
    assert len(windows_5s[0][1]) == 5 * sr

    # 2. 12 seconds: 0-5s, 5-10s, remaining 2s is skipped (< 3s)
    wave_12s = np.zeros(12 * sr, dtype=np.float32)
    windows_12s = slice_waveform_windows(wave_12s, sr=sr)
    assert len(windows_12s) == 2
    assert windows_12s[0][0] == 0.0
    assert windows_12s[1][0] == 5.0

    # 3. 13.5 seconds: 0-5s, 5-10s, remaining 3.5s is kept (>= 3s)
    wave_13_5s = np.zeros(int(13.5 * sr), dtype=np.float32)
    windows_13_5s = slice_waveform_windows(wave_13_5s, sr=sr)
    assert len(windows_13_5s) == 3
    assert windows_13_5s[0][0] == 0.0
    assert windows_13_5s[1][0] == 5.0
    assert windows_13_5s[2][0] == 10.0
    assert len(windows_13_5s[2][1]) == int(3.5 * sr)

    # 4. Short audio (2.5 seconds): skipped completely (< 3s)
    wave_2_5s = np.zeros(int(2.5 * sr), dtype=np.float32)
    windows_2_5s = slice_waveform_windows(wave_2_5s, sr=sr)
    assert len(windows_2_5s) == 0
