import numpy as np
from training.augment import DataAugmenter

def test_augmenter_length_and_dtype():
    y = np.random.normal(0, 0.1, 16000 * 2).astype(np.float32)
    augmenter = DataAugmenter(
        p_bandpass=1.0,
        p_resample=1.0,
        p_mulaw=1.0,
        p_codec=1.0,
        p_noise=1.0,
        p_gain=1.0,
        p_packetloss=1.0,
        p_reverb=1.0
    )
    
    y_out = augmenter(y)
    
    assert len(y_out) == len(y)
    assert y_out.dtype == np.float32
    assert not np.isnan(y_out).any()
