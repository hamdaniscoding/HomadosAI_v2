import os
import sys
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score, roc_curve
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.detectors.hf_audio import HFAudioDetector
from app.core.vad import measure_speech_seconds
from scripts.telephony_sim import apply_bandpass_resample, apply_mulaw
import librosa

def get_rms(y):
    return float(np.sqrt(np.mean(y**2)))

def main():
    models = [
        ("A", "abhishtagatya/wav2vec2-base-960h-itw-deepfake", "spoof"),
        ("B", "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification", "fake")
    ]
    
    conditions = ["original", "bandpass", "bandpass_mulaw"]
    
    files_to_process = []
    
    # Collect human files
    for path in glob.glob("data/human/*.mp3") + glob.glob("data/human/*.wav"):
        files_to_process.append({"path": path, "class": "human", "tool": "none"})
        
    # Collect AI files
    for path in glob.glob("data/ai/**/*.*", recursive=True):
        if path.endswith(".mp3") or path.endswith(".wav"):
            rel_path = Path(path).relative_to("data/ai")
            parts = rel_path.parts
            tool = parts[0] if len(parts) > 1 else "unknown"
            files_to_process.append({"path": path, "class": "ai", "tool": tool})
            
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    results = []
    
    for model_name, model_id, fake_label in models:
        print(f"Loading Model {model_name}...")
        try:
            detector = HFAudioDetector(model_id=model_id, fake_label=fake_label, device="cuda")
            detector.load()
        except Exception as e:
            print(f"Failed to load model {model_name}: {e}")
            continue
            
        for f in files_to_process:
            y_orig, sr = librosa.load(f["path"], sr=16000, mono=True)
            if len(y_orig) > 16000 * 60:
                y_orig = y_orig[:16000 * 60]
                
            y_bp = apply_bandpass_resample(y_orig, sr)
            y_mu = apply_mulaw(y_bp)
            
            y_dict = {
                "original": y_orig,
                "bandpass": y_bp,
                "bandpass_mulaw": y_mu
            }
            
            # Additional window lengths check
            window_lengths = [5]
            if f["class"] == "ai" or f["class"] == "human":
                window_lengths.extend([3, 10])
                
            for cond in conditions:
                y_c = y_dict[cond]
                
                for wl in window_lengths:
                    step = 16000 # 1 s hop
                    win_len = 16000 * wl
                    print(f"  {cond} len={wl}...", end=" ", flush=True)
                    count = 0
                    for i in range(0, len(y_c) - win_len + 1, step):
                        window = y_c[i:i+win_len]
                        if len(window) < win_len:
                            break
                        
                        score = float(detector.predict(window))
                        rms = get_rms(window)
                        speech_ratio = measure_speech_seconds(window, 16000) / wl
                        
                        t_start = i / 16000.0
                        
                        results.append({
                            "model": model_name,
                            "condition": cond,
                            "file": f["path"],
                            "class": f["class"],
                            "tool": f["tool"],
                            "t_start": t_start,
                            "window_len": wl,
                            "score": score,
                            "rms": rms,
                            "speech_ratio": speech_ratio
                        })
                        count += 1
                    print(f"{count} windows")

    df = pd.DataFrame(results)
    df.to_csv(reports_dir / "eval_001_windows.csv", index=False)
    
    # Process for window_len == 5
    df5 = df[df["window_len"] == 5]
    
    # 1. Per file output
    file_stats = df5.groupby(["model", "condition", "file"]).agg(
        mean_score=("score", "mean"),
        median_score=("score", "median"),
        min_score=("score", "min"),
        max_score=("score", "max"),
        frac_gt_05=("score", lambda x: (x > 0.5).mean())
    ).reset_index()
    
    # 2. Per model and condition output
    summary = []
    
    for (model, cond), group in df5.groupby(["model", "condition"]):
        # window level
        y_true_win = (group["class"] == "ai").astype(int)
        y_scores_win = group["score"]
        
        try:
            win_auc = roc_auc_score(y_true_win, y_scores_win)
            fpr, tpr, thresholds = roc_curve(y_true_win, y_scores_win)
            win_eer = fpr[np.nanargmin(np.abs(fpr - (1 - tpr)))]
        except ValueError:
            win_auc = 0.5
            win_eer = 0.5
            
        # file level (mean score)
        file_group = group.groupby(["file", "class"]).agg({"score": "mean"}).reset_index()
        y_true_file = (file_group["class"] == "ai").astype(int)
        y_scores_file = file_group["score"]
        try:
            file_auc = roc_auc_score(y_true_file, y_scores_file)
        except ValueError:
            file_auc = 0.5
            
        class_counts = group["class"].value_counts().to_dict()
        file_class_counts = file_group["class"].value_counts().to_dict()
        tool_counts = group[group["class"] == "ai"]["tool"].value_counts().to_dict()
        
        summary.append({
            "model": model,
            "condition": cond,
            "win_auc": win_auc,
            "win_eer": win_eer,
            "file_auc": file_auc,
            "windows_human": class_counts.get("human", 0),
            "windows_ai": class_counts.get("ai", 0),
            "files_human": file_class_counts.get("human", 0),
            "files_ai": file_class_counts.get("ai", 0),
            "tool_counts": tool_counts
        })
        
    summary_df = pd.DataFrame(summary)
    
    # 4. Variance diagnosis
    var_diag = {}
    for model in ["A", "B"]:
        mdf = df5[df5["model"] == model]
        if mdf.empty: continue
        
        corr_rms = mdf["score"].corr(mdf["rms"])
        corr_speech = mdf["score"].corr(mdf["speech_ratio"])
        
        ai_df = mdf[mdf["class"] == "ai"]
        below_01 = ai_df[ai_df["score"] < 0.1]
        above_09 = ai_df[ai_df["score"] > 0.9]
        
        # extra check windows
        df_all_w = df[df["model"] == model]
        spreads = df_all_w.groupby("window_len")["score"].std().to_dict()
        
        var_diag[model] = {
            "corr_rms": float(corr_rms) if pd.notna(corr_rms) else 0.0,
            "corr_speech": float(corr_speech) if pd.notna(corr_speech) else 0.0,
            "ai_below_0.1_count": len(below_01),
            "ai_below_0.1_mean_speech_ratio": float(below_01["speech_ratio"].mean()) if len(below_01) > 0 else 0.0,
            "ai_above_0.9_count": len(above_09),
            "ai_above_0.9_mean_speech_ratio": float(above_09["speech_ratio"].mean()) if len(above_09) > 0 else 0.0,
            "std_by_window_len": spreads
        }
        
    with open(reports_dir / "eval_001.json", "w") as f:
        json.dump({
            "summary": summary_df.to_dict(orient="records"),
            "variance_diagnosis": var_diag
        }, f, indent=2)
        
    with open(reports_dir / "eval_001.md", "w") as f:
        f.write("# Smoke Test Evaluation (Phase A)\n\n")
        f.write("NOTE: This is a smoke test with very few files, not an accuracy claim.\n\n")
        
        f.write("## Condition Summary\n")
        f.write(summary_df.to_markdown(index=False) + "\n\n")
        
        f.write("## Variance Diagnosis\n")
        for m, v in var_diag.items():
            f.write(f"### Model {m}\n")
            f.write(f"- Correlation (score, rms): {v['corr_rms']:.4f}\n")
            f.write(f"- Correlation (score, speech_ratio): {v['corr_speech']:.4f}\n")
            f.write(f"- AI windows < 0.1: {v['ai_below_0.1_count']} (mean speech_ratio={v['ai_below_0.1_mean_speech_ratio']:.4f})\n")
            f.write(f"- AI windows > 0.9: {v['ai_above_0.9_count']} (mean speech_ratio={v['ai_above_0.9_mean_speech_ratio']:.4f})\n")
            f.write(f"- Std deviation by window len: {v['std_by_window_len']}\n\n")

if __name__ == "__main__":
    main()
