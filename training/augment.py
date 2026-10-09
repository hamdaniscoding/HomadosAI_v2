import numpy as np
import librosa
import random
import scipy.signal

def bandpass_filter(y, sr, low=300, high=3400):
    nyq = 0.5 * sr
    low = low / nyq
    high = high / nyq
    b, a = scipy.signal.butter(4, [low, high], btype='band')
    return scipy.signal.lfilter(b, a, y)

def apply_mulaw(y):
    # simple mu-law companding
    mu = 255.0
    y_mu = np.sign(y) * np.log1p(mu * np.abs(y)) / np.log1p(mu)
    # expand
    y_expanded = np.sign(y_mu) * (1 / mu) * ((1 + mu) ** np.abs(y_mu) - 1)
    return y_expanded

def add_noise(y):
    noise = np.random.randn(len(y))
    snr = random.uniform(15, 30)
    signal_power = np.mean(y**2)
    noise_power = np.mean(noise**2)
    factor = np.sqrt(signal_power / noise_power) * (10 ** (-snr / 20))
    return y + factor * noise

def apply_random_gain(y):
    gain = random.uniform(0.5, 2.0)
    return y * gain

def augment_audio(y, sr):
    if random.random() < 0.3:
        y = bandpass_filter(y, sr)
    if random.random() < 0.3:
        y = apply_mulaw(y)
    if random.random() < 0.3:
        y = add_noise(y)
    if random.random() < 0.3:
        y = apply_random_gain(y)
    return y

def loudness_normalize(y, target_db=-23):
    rms = np.sqrt(np.mean(y**2))
    if rms == 0: return y
    db = 20 * np.log10(rms + 1e-6)
    gain = 10 ** ((target_db - db) / 20)
    return y * gain
