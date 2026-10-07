import pytest
from app.detectors.hf_audio import HFAudioDetector
import numpy as np

def test_load_trained_detector():
    detector = HFAudioDetector(
        model_id="models/hf_cache/my-detector",
        fake_label="fake",
        device="cpu"
    )
    
    detector.load()
    assert detector.model is not None
    
    # 5 seconds of silence
    dummy_audio = np.zeros(16000 * 5, dtype=np.float32)
    score = detector.predict(dummy_audio)
    
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
