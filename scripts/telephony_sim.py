import os
import sys
import numpy as np
import scipy.signal as signal
import librosa
import soundfile as sf
import subprocess
import tempfile
from pathlib import Path

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def apply_bandpass_resample(y, sr=16000):
    nyq = 0.5 * sr
    b, a = signal.butter(5, [300 / nyq, 3400 / nyq], btype='band')
    y_filtered = signal.filtfilt(b, a, y)
    
    y_8k = librosa.resample(y_filtered, orig_sr=sr, target_sr=8000)
    y_16k = librosa.resample(y_8k, orig_sr=8000, target_sr=16000)
    
    if len(y_16k) > len(y):
        y_16k = y_16k[:len(y)]
    elif len(y_16k) < len(y):
        y_16k = np.pad(y_16k, (0, len(y) - len(y_16k)))
    return y_16k

def apply_mulaw(y):
    mu = 255.0
    y_mu = np.sign(y) * np.log(1 + mu * np.abs(y)) / np.log(1 + mu)
    y_quant = np.round(y_mu * 127) / 127.0
    y_exp = np.sign(y_quant) * (1 / mu) * ((1 + mu)**np.abs(y_quant) - 1)
    return y_exp

def apply_codec(y, sr, codec, bitrate):
    fd_in, in_path = tempfile.mkstemp(suffix='.wav')
    fd_out, out_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd_in)
    os.close(fd_out)
    
    try:
        sf.write(in_path, y, sr)
        if codec == 'opus':
            out_encoded = out_path + '.webm'
            cmd_enc = ['ffmpeg', '-y', '-i', in_path, '-c:a', 'libopus', '-b:a', bitrate, out_encoded]
        elif codec == 'mp3':
            out_encoded = out_path + '.mp3'
            cmd_enc = ['ffmpeg', '-y', '-i', in_path, '-c:a', 'libmp3lame', '-b:a', bitrate, out_encoded]
            
        subprocess.run(cmd_enc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        cmd_dec = ['ffmpeg', '-y', '-i', out_encoded, '-ar', str(sr), out_path]
        subprocess.run(cmd_dec, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        y_out, _ = sf.read(out_path)
        if len(y_out) > len(y):
            y_out = y_out[:len(y)]
        elif len(y_out) < len(y):
            y_out = np.pad(y_out, (0, len(y) - len(y_out)))
            
        if os.path.exists(out_encoded):
            os.remove(out_encoded)
            
        return y_out
    finally:
        if os.path.exists(in_path): os.remove(in_path)
        if os.path.exists(out_path): os.remove(out_path)

def test_signal_processing():
    sr = 16000
    t = np.linspace(0, 1, sr)
    # Generate 1 kHz and 5 kHz mix
    y = np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 5000 * t)
    
    y_bp = apply_bandpass_resample(y, sr)
    assert len(y_bp) == len(y), "Length mismatch in bandpass"
    
    # FFT check: energy at 5kHz should be attenuated
    f = np.fft.rfftfreq(len(y), 1/sr)
    S_orig = np.abs(np.fft.rfft(y))
    S_bp = np.abs(np.fft.rfft(y_bp))
    idx_5k = np.argmin(np.abs(f - 5000))
    
    assert S_bp[idx_5k] < 0.1 * S_orig[idx_5k], "High frequency not attenuated enough"
    print("Unit tests passed.")

def process_and_save():
    has_ffmpeg = check_ffmpeg()
    
    variants = ["a_bandpass", "b_bandpass_mulaw"]
    if has_ffmpeg:
        variants.extend(["c_opus_12k", "c_mp3_32k"])
    else:
        print("ffmpeg not found in PATH, skipping opus and mp3 variants.")
        
    human_dir = Path("data/human")
    if not human_dir.exists():
        print("No human directory")
        return []
        
    files = list(human_dir.glob("*.mp3")) + list(human_dir.glob("*.wav"))
    results_map = {}
    
    for f in files:
        y, sr = librosa.load(f, sr=16000, mono=True)
        # up to first 60 seconds
        if len(y) > sr * 60:
            y = y[:sr * 60]
            
        results_map[f.name] = {"original": y}
        
        for v in variants:
            out_dir = Path(f"data/augmented/{v}")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / (f.stem + ".wav")
            
            if v == "a_bandpass":
                y_v = apply_bandpass_resample(y, sr)
            elif v == "b_bandpass_mulaw":
                y_bp = apply_bandpass_resample(y, sr)
                y_v = apply_mulaw(y_bp)
            elif v == "c_opus_12k":
                y_v = apply_codec(y, sr, 'opus', '12k')
            elif v == "c_mp3_32k":
                y_v = apply_codec(y, sr, 'mp3', '32k')
                
            sf.write(out_path, y_v, sr)
            results_map[f.name][v] = y_v
            
    return results_map, variants

def main():
    if "--test" in sys.argv:
        test_signal_processing()
        return

    print("Starting processing...")
    results_map, variants = process_and_save()
    
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "backend"))
    from app.detectors.hf_audio import HFAudioDetector
    
    models = [
        ("A", "abhishtagatya/wav2vec2-base-960h-itw-deepfake", "spoof"),
        ("B", "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification", "fake")
    ]
    
    for model_name, model_id, fake_label in models:
        print(f"\n--- Model {model_name} ---")
        try:
            detector = HFAudioDetector(model_id=model_id, fake_label=fake_label, device="cuda")
            detector.load()
        except Exception as e:
            print(f"Failed to load {model_name}: {e}")
            continue
            
        print(f"{'File':<15} | {'Variant':<20} | {'Mean Fake':<10} | {'Frac >0.5':<10} | {'Change (Abs)':<12}")
        print("-" * 75)
        
        for fname, var_audio in results_map.items():
            # Original score
            y_orig = var_audio["original"]
            windows_orig = [y_orig[i:i+16000*5] for i in range(0, len(y_orig), 16000*5) if len(y_orig[i:i+16000*5]) >= 16000*3]
            if not windows_orig:
                continue
            orig_scores = [detector.predict(w) for w in windows_orig]
            orig_mean = np.mean(orig_scores)
            orig_frac = np.mean(np.array(orig_scores) > 0.5)
            
            print(f"{fname[:15]:<15} | {'original':<20} | {orig_mean:<10.4f} | {orig_frac:<10.4f} | {'-':<12}")
            
            for v in variants:
                y_v = var_audio[v]
                windows_v = [y_v[i:i+16000*5] for i in range(0, len(y_v), 16000*5) if len(y_v[i:i+16000*5]) >= 16000*3]
                if not windows_v:
                    continue
                v_scores = [detector.predict(w) for w in windows_v]
                v_mean = np.mean(v_scores)
                v_frac = np.mean(np.array(v_scores) > 0.5)
                
                diff = v_mean - orig_mean
                diff_str = f"{diff:+.4f}"
                print(f"{fname[:15]:<15} | {v:<20} | {v_mean:<10.4f} | {v_frac:<10.4f} | {diff_str:<12}")

if __name__ == "__main__":
    main()
