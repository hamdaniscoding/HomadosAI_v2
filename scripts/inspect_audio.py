import os
import glob
import numpy as np
import librosa
from pathlib import Path

def effective_bandwidth(y, sr):
    if len(y) == 0:
        return 0
    S = np.abs(np.fft.rfft(y))**2
    freqs = np.fft.rfftfreq(len(y), 1/sr)
    cumsum = np.cumsum(S)
    total = cumsum[-1]
    if total == 0:
        return 0
    idx = np.searchsorted(cumsum, 0.99 * total)
    return freqs[idx]

def compute_rms(y):
    return np.sqrt(np.mean(y**2))

def process_file(path):
    y, sr = librosa.load(path, sr=None, mono=False)
    
    if y.ndim == 1:
        channels = 1
        duration = len(y) / sr
        peak = float(np.max(np.abs(y)))
        rms = float(compute_rms(y))
        bw = float(effective_bandwidth(y, sr))
        
        bw_guess = "likely phone" if bw <= 4500 else "likely wideband"
        guess = f"Guess: {bw_guess}"
        
        return [str(path), duration, sr, channels, peak, rms, bw, "", "", "", guess]
    else:
        channels = y.shape[0]
        duration = y.shape[1] / sr
        peak = float(np.max(np.abs(y)))
        rms = float(compute_rms(y))
        bw = float(effective_bandwidth(np.mean(y, axis=0), sr))
        
        ch_rms = [compute_rms(y[c]) for c in range(channels)]
        
        if channels == 2:
            corr = np.corrcoef(y[0], y[1])[0, 1] if np.std(y[0]) > 0 and np.std(y[1]) > 0 else 0.0
            
            frame_len = sr
            num_frames = y.shape[1] // frame_len
            split_frames = 0
            for i in range(num_frames):
                frame0 = y[0, i*frame_len:(i+1)*frame_len]
                frame1 = y[1, i*frame_len:(i+1)*frame_len]
                rms0 = compute_rms(frame0)
                rms1 = compute_rms(frame1)
                
                if min(rms0, rms1) > 0:
                    db_diff = np.abs(20 * np.log10(rms0 / rms1))
                    if db_diff > 6:
                        split_frames += 1
                elif max(rms0, rms1) > 0:
                    split_frames += 1
                    
            frac_6db = split_frames / num_frames if num_frames > 0 else 0.0
            
            bw_guess = "likely phone" if bw <= 4500 else "likely wideband"
            ch_guess = "likely one speaker per channel" if frac_6db > 0.1 else "likely mixed"
            guess = f"Guess: {bw_guess} / {ch_guess}"
            
            return [str(path), duration, sr, channels, peak, rms, bw, f"{ch_rms[0]:.4f}, {ch_rms[1]:.4f}", corr, frac_6db, guess]
        else:
            return [str(path), duration, sr, channels, peak, rms, bw, str(ch_rms), "", "", ""]

def main():
    base_dir = Path("data")
    if not base_dir.exists():
        print("No data directory found.")
        return
        
    results = []
    for ext in ['**/*.wav', '**/*.flac', '**/*.mp3']:
        for path in base_dir.glob(ext):
            try:
                res = process_file(path)
                results.append(res)
            except Exception as e:
                print(f"Error processing {path}: {e}")
                
    if not results:
        print("No audio files found.")
        return
        
    # Format and print table manually to avoid tabulate dependency
    headers = ["Path", "Dur(s)", "SR", "Ch", "Peak", "RMS", "BW(Hz)", "Ch RMS", "Corr", "Frac>6dB", "Heuristic"]
    # Convert all to string with formatting
    str_results = []
    for r in results:
        str_r = [
            r[0],
            f"{r[1]:.2f}",
            str(r[2]),
            str(r[3]),
            f"{r[4]:.4f}",
            f"{r[5]:.4f}",
            f"{r[6]:.0f}",
            r[7],
            f"{r[8]:.4f}" if isinstance(r[8], float) else r[8],
            f"{r[9]:.4f}" if isinstance(r[9], float) else r[9],
            r[10]
        ]
        str_results.append(str_r)
        
    col_widths = [max(len(str(item)) for item in col) for col in zip(*([headers] + str_results))]
    
    header_row = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    print(header_row)
    print("-" * len(header_row))
    for row in str_results:
        print(" | ".join(f"{item:<{w}}" for item, w in zip(row, col_widths)))

if __name__ == "__main__":
    main()
