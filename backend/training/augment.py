import random
import numpy as np
import scipy.signal
import torch
import torchaudio
import subprocess
import os
import tempfile
import imageio_ffmpeg
import soundfile as sf
from typing import Optional

def apply_bandpass(y: np.ndarray, sr: int, lowcut: float = 300.0, highcut: float = 3400.0) -> np.ndarray:
    nyq = 0.5 * sr
    low = lowcut / nyq
    high = min(highcut / nyq, 0.99)
    if low >= high:
        return y
    b, a = scipy.signal.butter(5, [low, high], btype='band')
    return scipy.signal.lfilter(b, a, y).astype(np.float32)

def apply_resample_8k(y: np.ndarray, sr: int) -> np.ndarray:
    if sr <= 8000:
        return y
    tensor_y = torch.from_numpy(y)
    down = torchaudio.functional.resample(tensor_y, sr, 8000)
    up = torchaudio.functional.resample(down, 8000, sr)
    return up.numpy().astype(np.float32)

def apply_mulaw(y: np.ndarray) -> np.ndarray:
    tensor_y = torch.from_numpy(y)
    encoded = torchaudio.functional.mu_law_encoding(tensor_y, quantization_channels=256)
    decoded = torchaudio.functional.mu_law_decoding(encoded, quantization_channels=256)
    return decoded.numpy().astype(np.float32)

def apply_codec(y: np.ndarray, sr: int, codec: str, bitrate: str = "32k") -> np.ndarray:
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return y
    
    with tempfile.TemporaryDirectory() as d:
        in_path = os.path.join(d, "in.wav")
        out_path = os.path.join(d, f"out.{'mp3' if codec == 'mp3' else 'opus'}")
        
        sf.write(in_path, y, sr)
        
        codec_name = "libmp3lame" if codec == "mp3" else "libopus"
        cmd = [
            exe, "-y", "-i", in_path, 
            "-c:a", codec_name, 
            "-b:a", bitrate, 
            out_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out_y, _ = sf.read(out_path)
            # Match length
            if len(out_y) > len(y):
                out_y = out_y[:len(y)]
            elif len(out_y) < len(y):
                out_y = np.pad(out_y, (0, len(y) - len(out_y)))
            return out_y.astype(np.float32)
        except Exception:
            return y

def apply_noise(y: np.ndarray, snr_db: float) -> np.ndarray:
    signal_power = np.mean(y**2)
    if signal_power == 0:
        return y
    snr_linear = 10 ** (snr_db / 10)
    noise_power = signal_power / snr_linear
    noise = np.random.normal(0, np.sqrt(noise_power), len(y))
    return (y + noise).astype(np.float32)

def apply_gain(y: np.ndarray, gain_db: float) -> np.ndarray:
    return (y * (10 ** (gain_db / 20))).astype(np.float32)

def apply_packet_loss(y: np.ndarray, sr: int) -> np.ndarray:
    y_out = y.copy()
    # 1 to 3 short gaps (10-50ms)
    n_gaps = random.randint(1, 3)
    for _ in range(n_gaps):
        gap_dur = random.uniform(0.01, 0.05)
        gap_samples = int(gap_dur * sr)
        if len(y) > gap_samples:
            start = random.randint(0, len(y) - gap_samples)
            y_out[start:start+gap_samples] = 0
    return y_out

def apply_reverb(y: np.ndarray) -> np.ndarray:
    # Very simple light exponential decay
    impulse_len = 1000
    decay = np.exp(-np.linspace(0, 5, impulse_len))
    noise = np.random.normal(0, 1, impulse_len)
    ir = (decay * noise).astype(np.float32)
    ir /= np.sum(np.abs(ir))
    
    y_rev = scipy.signal.convolve(y, ir, mode='full')[:len(y)]
    # Mix dry and wet
    return (y * 0.7 + y_rev * 0.3).astype(np.float32)

class DataAugmenter:
    def __init__(
        self,
        sr: int = 16000,
        p_bandpass: float = 0.2,
        p_resample: float = 0.2,
        p_mulaw: float = 0.2,
        p_codec: float = 0.3,
        p_noise: float = 0.3,
        p_gain: float = 0.3,
        p_packetloss: float = 0.2,
        p_reverb: float = 0.2
    ):
        self.sr = sr
        self.p_bandpass = p_bandpass
        self.p_resample = p_resample
        self.p_mulaw = p_mulaw
        self.p_codec = p_codec
        self.p_noise = p_noise
        self.p_gain = p_gain
        self.p_packetloss = p_packetloss
        self.p_reverb = p_reverb
        
    def __call__(self, y: np.ndarray) -> np.ndarray:
        # Expect float32
        original_len = len(y)
        
        if random.random() < self.p_bandpass:
            y = apply_bandpass(y, self.sr)
            
        if random.random() < self.p_resample:
            y = apply_resample_8k(y, self.sr)
            
        if random.random() < self.p_mulaw:
            y = apply_mulaw(y)
            
        if random.random() < self.p_codec:
            codec = random.choice(["mp3", "opus"])
            y = apply_codec(y, self.sr, codec)
            
        if random.random() < self.p_noise:
            snr = random.uniform(5, 30)
            y = apply_noise(y, snr)
            
        if random.random() < self.p_gain:
            gain = random.uniform(-10, 10)
            y = apply_gain(y, gain)
            
        if random.random() < self.p_packetloss:
            y = apply_packet_loss(y, self.sr)
            
        if random.random() < self.p_reverb:
            y = apply_reverb(y)
            
        # Ensure length
        if len(y) > original_len:
            y = y[:original_len]
        elif len(y) < original_len:
            y = np.pad(y, (0, original_len - len(y)))
            
        # Clip to [-1, 1]
        y = np.clip(y, -1.0, 1.0)
        return y.astype(np.float32)
