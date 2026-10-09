import sys, os, glob
from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
import json
from sklearn.metrics import roc_auc_score

def compute_snr(y):
    stft = np.abs(librosa.stft(y))
    power = np.sum(stft**2, axis=0)
    noise_power = np.percentile(power, 10)
    if noise_power == 0: return 50.0
    return float(10 * np.log10(np.mean(power) / noise_power))

def get_silence(y, sr):
    non_silent = librosa.effects.split(y, top_db=40)
    if len(non_silent) == 0:
        return 0.0, 0.0
    start_silence = non_silent[0][0] / sr
    end_silence = (len(y) - non_silent[-1][1]) / sr
    return float(start_silence), float(end_silence)

def audit():
    human = glob.glob('data/human/**/*.*', recursive=True)
    ai = glob.glob('data/ai/**/*.*', recursive=True)
    
    data = []
    
    for label, files in [(0, human), (1, ai)]:
        for f in files:
            if not os.path.isfile(f) or not f.endswith(('.wav', '.mp3', '.ogg', '.opus', '.flac')): continue
            
            try:
                info = sf.info(f)
                sr_orig = info.samplerate
                duration = info.duration
                
                y, sr = librosa.load(f, sr=None, mono=True)
                rms = float(np.sqrt(np.mean(y**2)))
                snr = compute_snr(y)
                
                start_sil, end_sil = get_silence(y, sr)
                
                spec_bw = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
                rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
                
                tool = "Unknown"
                if 'piper' in f: tool = "Piper"
                elif 'a' in os.path.basename(f) and label == 1: tool = "Synthetic (Unknown)"
                
                data.append({
                    'file': f,
                    'label': label,
                    'sr_orig': sr_orig,
                    'duration': duration,
                    'rms': rms,
                    'snr': snr,
                    'start_silence': start_sil,
                    'end_silence': end_sil,
                    'spectral_bandwidth': spec_bw,
                    'rolloff': rolloff,
                    'tool': tool
                })
            except Exception as e:
                print(f"Failed to process {f}: {e}")

    with open('reports/audit_raw.json', 'w') as f:
        json.dump(data, f)
        
    human_data = [d for d in data if d['label'] == 0]
    ai_data = [d for d in data if d['label'] == 1]
    
    if not human_data or not ai_data:
        print("Missing data for audit")
        return
        
    features = ['sr_orig', 'duration', 'rms', 'snr', 'start_silence', 'end_silence', 'spectral_bandwidth', 'rolloff']
    
    labels = [d['label'] for d in data]
    
    shortcuts = []
    
    report = "# Data Audit Report\n\n"
    report += "Feature | Human Mean | AI Mean | AUC\n"
    report += "---|---|---|---\n"
    
    for feat in features:
        vals = [d[feat] for d in data]
        h_vals = [d[feat] for d in human_data]
        a_vals = [d[feat] for d in ai_data]
        auc = roc_auc_score(labels, vals)
        if auc < 0.5: auc = 1 - auc
        
        report += f"{feat} | {np.mean(h_vals):.2f} | {np.mean(a_vals):.2f} | {auc:.2f}\n"
        if auc > 0.8:
            shortcuts.append((feat, auc))
            
    report += "\n## Shortcuts Found (AUC > 0.8)\n"
    if shortcuts:
        for feat, auc in shortcuts:
            report += f"- **{feat}** (AUC: {auc:.2f})\n"
    else:
        report += "None found.\n"
        
    tools = list(set(d['tool'] for d in ai_data))
    report += f"\n## AI Tools/Speakers\nDistinct AI tools found: {len(tools)} ({tools})\n"
    
    report += """
## Recommendations
1. **Loudness Normalization**: Normalize RMS identically for both classes.
2. **Band-limiting**: Low-pass filter both classes to 8 kHz to remove codec high-frequency signatures.
3. **Codec augmentation**: Re-encode both classes randomly so original codecs aren't a shortcut.
"""
    with open('reports/data_audit.md', 'w') as f:
        f.write(report)
        
    print("Audit written to reports/data_audit.md")

if __name__ == '__main__':
    os.makedirs('reports', exist_ok=True)
    audit()
