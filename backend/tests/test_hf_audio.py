"""Plumbing tests for HFAudioDetector with random weights.

NOTE: This is a plumbing test with random weights, not a quality test.
It tests adapter instantiation, configuration validation, Hugging Face serialization,
and input sanity checking without downloading weights over the network.
"""

from __future__ import annotations

import numpy as np
import pytest
from transformers import (
    Wav2Vec2Config,
    Wav2Vec2FeatureExtractor,
    Wav2Vec2ForSequenceClassification,
)

from app.detectors import registry
from app.detectors.base import Detector
from app.detectors.hf_audio import HFAudioDetector
from app.main import init_detector


@pytest.fixture(scope="module")
def tiny_wav2vec2_model_dir(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Create and serialize a tiny Wav2Vec2 model with random weights (no network).

    This fixture creates a minimal Wav2Vec2 sequence classification model for plumbing tests.
    """
    model_dir = tmp_path_factory.mktemp("tiny_wav2vec2")
    cfg = Wav2Vec2Config(
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        num_labels=2,
        id2label={0: "real", 1: "fake"},
        label2id={"real": 0, "fake": 1},
    )
    model = Wav2Vec2ForSequenceClassification(cfg)
    fe = Wav2Vec2FeatureExtractor(sampling_rate=16000)

    model.save_pretrained(str(model_dir))
    fe.save_pretrained(str(model_dir))
    return str(model_dir)


def test_hf_audio_detector_plumbing_output_range(tiny_wav2vec2_model_dir: str):
    """Plumbing test with random weights, not a quality test.

    Verifies that HFAudioDetector implements Detector, loads from local disk,
    and returns a float probability in [0.0, 1.0].
    """
    detector = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label="fake",
        device="cpu",
        window_seconds=5.0,
    )
    assert isinstance(detector, Detector)
    assert detector.sample_rate == 16000
    assert detector.window_seconds == 5.0
    assert tiny_wav2vec2_model_dir in detector.name

    detector.load()

    # 5 seconds of 16 kHz audio
    waveform = np.sin(np.linspace(0, 100 * np.pi, 16000 * 5), dtype=np.float32) * 0.1
    prob = detector.predict(waveform)

    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_hf_audio_wrong_fake_label_raises(tiny_wav2vec2_model_dir: str):
    """Plumbing test: verify that an unrecognized fake_label refuses to load."""
    # Unknown label name
    detector = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label="nonexistent_label",
        device="cpu",
    )
    with pytest.raises(ValueError, match="fake_label 'nonexistent_label' not found in model id2label"):
        detector.load()

    # Out of range integer label
    detector_int = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label=999,
        device="cpu",
    )
    with pytest.raises(ValueError, match="fake_label class index 999 not found in model id2label"):
        detector_int.load()


def test_hf_audio_empty_fake_label_raises(tiny_wav2vec2_model_dir: str):
    """Plumbing test: verify that missing or empty fake_label raises at constructor time."""
    with pytest.raises(ValueError, match="fake_label is required"):
        HFAudioDetector(model_id=tiny_wav2vec2_model_dir, fake_label="", device="cpu")

    with pytest.raises(ValueError, match="fake_label is required"):
        HFAudioDetector(model_id=tiny_wav2vec2_model_dir, fake_label=None, device="cpu")  # type: ignore[arg-type]


def test_hf_audio_empty_input_raises(tiny_wav2vec2_model_dir: str):
    """Plumbing test: verify that empty input raises a clear error."""
    detector = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label="fake",
        device="cpu",
    )
    detector.load()

    with pytest.raises(ValueError, match="cannot be empty"):
        detector.predict(np.array([], dtype=np.float32))

    with pytest.raises(ValueError, match="cannot be None"):
        detector.predict(None)  # type: ignore[arg-type]


def test_hf_audio_wrong_sample_rate_raises(tiny_wav2vec2_model_dir: str):
    """Plumbing test: verify that incorrect sample rate raises a clear error."""
    detector = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label="fake",
        device="cpu",
    )
    detector.load()

    waveform = np.ones(16000, dtype=np.float32)
    with pytest.raises(ValueError, match="Wrong sample rate"):
        detector.predict(waveform, sample_rate=8000)


def test_hf_audio_int_fake_label(tiny_wav2vec2_model_dir: str):
    """Plumbing test: verify that integer class index works for fake_label."""
    detector = HFAudioDetector(
        model_id=tiny_wav2vec2_model_dir,
        fake_label=1,
        device="cpu",
    )
    detector.load()
    waveform = np.zeros(16000, dtype=np.float32)
    prob = detector.predict(waveform)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_startup_registration_with_settings(tiny_wav2vec2_model_dir: str, monkeypatch: pytest.MonkeyPatch):
    """Verify that if DETECTOR_MODEL_ID is set, init_detector registers HFAudioDetector."""
    from app.config import Settings

    custom_settings = Settings(
        detector_model_id=tiny_wav2vec2_model_dir,
        detector_fake_label="fake",
        torch_device="cpu",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: custom_settings)

    init_detector()
    active = registry.get_active()
    try:
        assert active is not None
        assert isinstance(active, HFAudioDetector)
        assert active.model_id == tiny_wav2vec2_model_dir
    finally:
        registry.unregister(active.name)
