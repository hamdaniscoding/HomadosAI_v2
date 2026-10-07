import os
import argparse
import torch
import pandas as pd
import numpy as np
import soundfile as sf
from training.train import AudioClassifier, compute_metrics
from training.augment import apply_bandpass, apply_mulaw
from pathlib import Path

def evaluate(checkpoint_path, csv_path, config_path):
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AudioClassifier(config["model_id"])
    model.to(device)
    
    ckpt = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    
    df = pd.read_csv(csv_path)
    
    conditions = ["original", "bandpass", "mulaw"]
    results = {cond: {"y_true": [], "y_score_win": [], "y_score_file": [], "source": []} for cond in conditions}
    
    sr = 16000
    window_samples = int(5.0 * sr)
    hop_samples = int(1.0 * sr)
    
    with torch.no_grad():
        for _, row in df.iterrows():
            y_orig, sr_orig = sf.read(row["path"])
            if y_orig.ndim > 1:
                y_orig = y_orig.mean(axis=1)
            
            if sr_orig != sr:
                import torchaudio
                y_orig = torchaudio.functional.resample(torch.from_numpy(y_orig), sr_orig, sr).numpy()
                
            label = row["label"]
            source = row["source"]
            
            for cond in conditions:
                if cond == "original":
                    y = y_orig.copy()
                elif cond == "bandpass":
                    y = apply_bandpass(y_orig.copy(), sr)
                elif cond == "mulaw":
                    y = apply_mulaw(y_orig.copy())
                    
                y = y.astype(np.float32)
                
                # window level scores
                win_scores = []
                for i in range(0, max(1, len(y) - window_samples + 1), hop_samples):
                    win = y[i:i+window_samples]
                    if len(win) < window_samples:
                        win = np.pad(win, (0, window_samples - len(win)))
                    
                    x = torch.from_numpy(win).unsqueeze(0).to(device)
                    logits = model(x)
                    probs = torch.softmax(logits, dim=-1)[0, 1].item()
                    win_scores.append(probs)
                    results[cond]["y_true"].append(label)
                    results[cond]["y_score_win"].append(probs)
                    results[cond]["source"].append(source)
                    
                # file level score (mean of windows)
                if win_scores:
                    file_score = np.mean(win_scores)
                    results[cond]["y_score_file"].append(file_score)
                else:
                    results[cond]["y_score_file"].append(0.5)
                    
    # Print report
    for cond in conditions:
        print(f"\n--- Condition: {cond} ---")
        y_true_file = df["label"].tolist()
        auc_f, eer_f = compute_metrics(y_true_file, results[cond]["y_score_file"])
        print(f"File-level   -> AUC: {auc_f:.4f} | EER: {eer_f:.4f}")
        
        auc_w, eer_w = compute_metrics(results[cond]["y_true"], results[cond]["y_score_win"])
        print(f"Window-level -> AUC: {auc_w:.4f} | EER: {eer_w:.4f}")
        
        # Per source (file level is trickier because we need to group by source, let's do window-level per source)
        df_win = pd.DataFrame({
            "true": results[cond]["y_true"],
            "score": results[cond]["y_score_win"],
            "source": results[cond]["source"]
        })
        for src, grp in df_win.groupby("source"):
            auc_s, eer_s = compute_metrics(grp["true"].tolist(), grp["score"].tolist())
            print(f"  Source: {src:<10} -> Win AUC: {auc_s:.4f} | Win EER: {eer_s:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"))
    args = parser.parse_args()
    evaluate(args.ckpt, args.csv, args.config)
