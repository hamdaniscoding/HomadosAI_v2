import sys
import os
import glob
import json
import torch
import numpy as np
import librosa
from sklearn.metrics import roc_auc_score, roc_curve

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.detectors.registry import get_active, list_detectors, register
from app.detectors.hf_audio import HFAudioDetector

def compute_metrics(y_true, y_probs):
    auc = roc_auc_score(y_true, y_probs)
    fpr, tpr, thresholds = roc_curve(y_true, y_probs)
    
    # EER
    fnr = 1 - tpr
    idx = np.nanargmin(np.absolute((fnr - fpr)))
    eer = fpr[idx]
    eer_thresh = thresholds[idx]
    
    # Accuracy at EER threshold
    preds = (np.array(y_probs) >= eer_thresh).astype(int)
    acc = np.mean(preds == y_true)
    
    # TPR at 1% FPR
    idx_1fpr = np.where(fpr <= 0.01)[0][-1] if len(np.where(fpr <= 0.01)[0]) > 0 else 0
    tpr_1fpr = tpr[idx_1fpr]
    
    return {
        "AUC": float(auc),
        "EER": float(eer),
        "EER_threshold": float(eer_thresh),
        "Accuracy_at_EER": float(acc),
        "TPR_at_1%_FPR": float(tpr_1fpr)
    }

def run_benchmark():
    human = glob.glob('data/human/**/*.*', recursive=True)[-5:]
    ai = glob.glob('data/ai/**/*.*', recursive=True)[-5:]
    
    data = []
    for f in human: data.append({'file': f, 'label': 0})
    for f in ai: data.append({'file': f, 'label': 1})
    
    # Load detectors
    detectors = []
    
    # We must init the detector using config or settings
    from app.config import get_settings
    settings = get_settings()
    
    if settings.detector_model_id:
        det = HFAudioDetector(
            model_id=settings.detector_model_id,
            fake_label=settings.detector_fake_label,
            device="cpu",
            window_seconds=settings.window_seconds,
        )
        detectors.append(det)
        
    results = {}
    for d in detectors:
        print(f"Benchmarking {d.name}...")
        y_true = []
        y_probs = []
        
        for item in data:
            f = item['file']
            try:
                y, sr = librosa.load(f, sr=16000, mono=True)
                win_len = 16000 * 5
                if len(y) > win_len:
                    start = (len(y) - win_len) // 2
                    y = y[start:start+win_len]
                else:
                    y = np.pad(y, (0, max(0, win_len - len(y))))
                    
                prob = d.predict(y)
                y_true.append(item['label'])
                y_probs.append(prob)
            except Exception as e:
                print(f"Error on {f}: {e}")
                
        metrics = compute_metrics(y_true, y_probs)
        results[d.name] = metrics
        
    os.makedirs('reports', exist_ok=True)
    with open('reports/benchmark.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    md = "# Detector Benchmarks\n\n"
    md += "Detector | AUC | EER | Acc@EER | TPR@1%FPR\n"
    md += "---|---|---|---|---\n"
    for name, m in results.items():
        md += f"{name} | {m['AUC']:.4f} | {m['EER']:.4f} | {m['Accuracy_at_EER']:.4f} | {m['TPR_at_1%_FPR']:.4f}\n"
        
    with open('reports/benchmark.md', 'w') as f:
        f.write(md)
        
    print("Results written to reports/benchmark.md")
    
if __name__ == '__main__':
    run_benchmark()
