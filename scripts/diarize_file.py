import sys
from pathlib import Path
import librosa
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.speaker.diarizer import OnlineDiarizer
from app.core.vad import measure_speech_seconds

def diarize_file(path: str):
    y, sr = librosa.load(path, sr=16000, mono=True)
    if len(y) > 16000 * 60:
        y = y[:16000 * 60]
        
    diarizer = OnlineDiarizer()
    
    # Process in 1.0s chunks
    hop = 1.0
    hop_samples = int(hop * sr)
    
    timeline = []
    current_spk = None
    current_start = 0.0
    
    for i in range(0, len(y) - hop_samples + 1, hop_samples):
        chunk = y[i:i+hop_samples]
        t = i / sr
        
        # We need 1.5s for diarization embedding if we follow the online logic exactly, 
        # but here we can just use 1.5s windows sliding by 1.0s hop
        diarize_win = y[max(0, i + hop_samples - int(1.5*sr)) : i + hop_samples]
        
        if measure_speech_seconds(diarize_win, sr) >= 0.5:
            spk_id = diarizer.process_segment(diarize_win)
        else:
            spk_id = None
            
        if spk_id != current_spk:
            if current_spk is not None:
                timeline.append((current_start, t, current_spk))
            current_start = t
            current_spk = spk_id
            
    if current_spk is not None:
        timeline.append((current_start, len(y)/sr, current_spk))
        
    print(f"\nTimeline for {Path(path).name}:")
    for start, end, spk in timeline:
        spk_str = f"Speaker {spk}" if spk is not None else "Silence/Unclustered"
        print(f"[{start:05.1f} - {end:05.1f}] {spk_str}")

def main():
    import glob
    for f in sorted(glob.glob("data/human/h*.mp3") + glob.glob("data/human/h*.wav")):
        diarize_file(f)

if __name__ == "__main__":
    main()
