#!/usr/bin/env python3
"""Score audio folders (human vs AI) using a pretrained speech detector.

Evaluates audio files split into 5-second non-overlapping windows and computes
window-level fake probabilities, file-level aggregates, ROC AUC, and EER.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch

# Ensure backend/ is in sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.audio import decode_upload
from app.detectors.hf_audio import HFAudioDetector

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
SAMPLE_RATE = 16000
WINDOW_SAMPLES = int(5.0 * SAMPLE_RATE)     # 80,000 samples (5.0 s)
MIN_WINDOW_SAMPLES = int(3.0 * SAMPLE_RATE) # 48,000 samples (3.0 s)


def compute_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Compute Area Under the Receiver Operating Characteristic (ROC AUC).

    Uses the Mann-Whitney U rank-sum formula in pure NumPy, handling ties.
    Returns float in [0.0, 1.0], or NaN if only one class is present.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)

    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    n_pos = len(pos)
    n_neg = len(neg)
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    # Compute ranks handling ties
    order = np.argsort(y_score)
    ranks = np.empty(len(y_score), dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1, dtype=float)

    unique_vals, inverse = np.unique(y_score, return_inverse=True)
    if len(unique_vals) < len(y_score):
        for i in range(len(unique_vals)):
            ranks[inverse == i] = np.mean(ranks[inverse == i])

    sum_rank_pos = np.sum(ranks[y_true == 1])
    u_pos = sum_rank_pos - (n_pos * (n_pos + 1)) / 2.0
    return float(u_pos / (n_pos * n_neg))


def compute_eer(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, float]:
    """Compute Equal Error Rate (EER) and the corresponding decision threshold.

    In fake voice detection:
      - Positive class (1) = AI / Spoof
      - Negative class (0) = Human / Bona-fide
      - Score = probability of being fake
      - FAR (False Acceptance Rate): Human incorrectly scored >= threshold
      - FRR (False Rejection Rate): AI incorrectly scored < threshold

    Returns (eer, threshold) in pure NumPy.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)

    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    n_pos = len(pos)
    n_neg = len(neg)
    if n_pos == 0 or n_neg == 0:
        return float("nan"), float("nan")

    # Distinct candidate thresholds
    thresholds = np.sort(np.unique(y_score))
    far = np.zeros(len(thresholds), dtype=float)
    frr = np.zeros(len(thresholds), dtype=float)

    for i, th in enumerate(thresholds):
        far[i] = np.sum(neg >= th) / n_neg
        frr[i] = np.sum(pos < th) / n_pos

    diff = far - frr
    min_idx = int(np.argmin(np.abs(diff)))

    # Linear interpolation at the crossing point
    if min_idx < len(thresholds) - 1 and diff[min_idx] * diff[min_idx + 1] <= 0:
        d1, d2 = diff[min_idx], diff[min_idx + 1]
        denom = d1 - d2
        if abs(denom) > 1e-12:
            t = d1 / denom
            eer = float(far[min_idx] + t * (far[min_idx + 1] - far[min_idx]))
            th_opt = float(thresholds[min_idx] + t * (thresholds[min_idx + 1] - thresholds[min_idx]))
        else:
            eer = float((far[min_idx] + frr[min_idx]) / 2.0)
            th_opt = float(thresholds[min_idx])
    else:
        eer = float((far[min_idx] + frr[min_idx]) / 2.0)
        th_opt = float(thresholds[min_idx])

    return float(np.clip(eer, 0.0, 1.0)), th_opt


def slice_waveform_windows(
    waveform: np.ndarray,
    window_samples: int = WINDOW_SAMPLES,
    min_samples: int = MIN_WINDOW_SAMPLES,
    sr: int = SAMPLE_RATE,
) -> list[tuple[float, np.ndarray]]:
    """Split waveform into non-overlapping 5-second windows.

    Skips a final window if shorter than min_samples (3.0 seconds).
    Returns list of (window_start_seconds, window_waveform).
    """
    total_len = len(waveform)
    windows: list[tuple[float, np.ndarray]] = []
    start = 0
    while start < total_len:
        end = start + window_samples
        chunk = waveform[start:end]
        if len(chunk) < min_samples:
            break
        start_sec = round(start / float(sr), 3)
        windows.append((start_sec, chunk))
        start = end
    return windows


def find_audio_files(directory: Path) -> list[Path]:
    """Find all supported audio files in a directory recursively."""
    if not directory.exists() or not directory.is_dir():
        return []
    files: list[Path] = []
    for item in sorted(directory.rglob("*")):
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(item)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score audio folders (human vs AI) using an HFAudioDetector."
    )
    parser.add_argument(
        "--model-id",
        type=str,
        required=True,
        help="Hugging Face hub ID or local folder path.",
    )
    parser.add_argument(
        "--fake-label",
        type=str,
        required=True,
        help="Class name or index corresponding to fake/spoof audio.",
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "cuda"],
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Computation device.",
    )
    parser.add_argument(
        "--human-dir",
        type=str,
        default="data/human",
        help="Path to folder containing real/human audio files (default: data/human).",
    )
    parser.add_argument(
        "--ai-dir",
        type=str,
        default="data/ai",
        help="Path to folder containing synthetic/AI audio files (default: data/ai).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/results/scores.csv",
        help="Path to output CSV file (default: data/results/scores.csv).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    human_dir = Path(args.human_dir)
    ai_dir = Path(args.ai_dir)
    out_path = Path(args.out)

    # Validate folders
    human_files = find_audio_files(human_dir)
    ai_files = find_audio_files(ai_dir)

    missing_errors: list[str] = []
    if not human_dir.exists():
        missing_errors.append(f"Human directory does not exist: '{human_dir}'")
    elif len(human_files) == 0:
        missing_errors.append(f"Human directory is empty (no supported audio found in '{human_dir}')")

    human_only_mode = False
    if not ai_dir.exists() or len(ai_files) == 0:
        human_only_mode = True

    if missing_errors:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Missing or empty human input dataset folders:", file=sys.stderr)
        for err in missing_errors:
            print(f"  - {err}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(1)
        
    if human_only_mode:
        print("=" * 70)
        print("NOTICE: AI folder is missing or empty. Running in HUMAN-ONLY scoring mode.")
        print("=" * 70)

    # Initialize and load detector
    parsed_fake_label: str | int = int(args.fake_label) if args.fake_label.isdigit() else args.fake_label
    print(f"Loading detector '{args.model_id}' on {args.device}...")
    detector = HFAudioDetector(
        model_id=args.model_id,
        fake_label=parsed_fake_label,
        device=args.device,
        window_seconds=5.0,
    )
    detector.load()

    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    file_averages: dict[str, dict[str, object]] = {}

    dataset = [("human", human_files)]
    if not human_only_mode:
        dataset.append(("ai", ai_files))

    print(f"Processing audio files (Human: {len(human_files)}, AI: {len(ai_files)})...")

    for label_name, files in dataset:
        for file_path in files:
            rel_name = str(file_path.as_posix())
            try:
                data = file_path.read_bytes()
                waveform, duration = decode_upload(data, file_path.name)
            except Exception as exc:
                print(f"WARNING: Failed to decode '{file_path}': {exc}", file=sys.stderr)
                continue

            windows = slice_waveform_windows(waveform)
            if len(windows) < 2:
                print(
                    f"WARNING: File '{rel_name}' produced {len(windows)} window(s) "
                    f"(duration: {duration:.2f}s). Fewer than 2 windows available.",
                    file=sys.stderr,
                )

            scores_for_file: list[float] = []
            for win_start_s, win_wave in windows:
                prob = detector.predict(win_wave)
                scores_for_file.append(prob)
                rows.append({
                    "file": rel_name,
                    "label": label_name,
                    "window_start_s": win_start_s,
                    "fake_probability": round(prob, 6),
                })

            if scores_for_file:
                file_averages[rel_name] = {
                    "label": label_name,
                    "windows": len(scores_for_file),
                    "mean_fake_prob": float(np.mean(scores_for_file)),
                    "median_fake_prob": float(np.median(scores_for_file)),
                    "min_fake_prob": float(np.min(scores_for_file)),
                    "max_fake_prob": float(np.max(scores_for_file)),
                    "frac_above_05": float(np.mean(np.array(scores_for_file) > 0.5))
                }

    # Write output CSV
    with open(out_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["file", "label", "window_start_s", "fake_probability"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} scored windows to '{out_path}'.")

    # Metrics and Summaries
    human_scores = [float(r["fake_probability"]) for r in rows if r["label"] == "human"]
    ai_scores = [float(r["fake_probability"]) for r in rows if r["label"] == "ai"]

    print("\n" + "=" * 70)
    print("HOMADOS AI · AUDIO EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Human files evaluated:    {len([f for f in file_averages.values() if f['label'] == 'human'])}")
    print(f"Human windows evaluated:  {len(human_scores)}")
    if human_scores:
        print(f"  Human fake prob (mean):   {np.mean(human_scores):.4f}")
        print(f"  Human fake prob (median): {np.median(human_scores):.4f}")

    print(f"\nAI files evaluated:       {len([f for f in file_averages.values() if f['label'] == 'ai'])}")
    print(f"AI windows evaluated:     {len(ai_scores)}")
    if ai_scores:
        print(f"  AI fake prob (mean):      {np.mean(ai_scores):.4f}")
        print(f"  AI fake prob (median):    {np.median(ai_scores):.4f}")

    if human_scores and ai_scores:
        y_true = np.array([0] * len(human_scores) + [1] * len(ai_scores))
        y_score = np.array(human_scores + ai_scores)
        auc = compute_roc_auc(y_true, y_score)
        eer, eer_th = compute_eer(y_true, y_score)
        print("\nWINDOW-LEVEL METRICS:")
        print(f"  ROC AUC:                  {auc:.4f}")
        print(f"  Equal Error Rate (EER):   {eer * 100:.2f}% (threshold = {eer_th:.4f})")

    print("\nPER-FILE METRICS:")
    for fname, info in file_averages.items():
        print(
            f"  [{info['label'].upper()}] {fname}: {info['windows']} win, "
            f"mean={info['mean_fake_prob']:.4f}, median={info['median_fake_prob']:.4f}, "
            f"min={info['min_fake_prob']:.4f}, max={info['max_fake_prob']:.4f}, "
            f"false-alarm rate at an arbitrary 0.5 threshold={info['frac_above_05']:.4f}"
        )

    print("\n" + "-" * 70)
    print(
        "IMPORTANT METHODOLOGICAL WARNING:\n"
        "EER reported above is computed naively across individual windows.\n"
        "In a scientifically valid benchmark, EER must be evaluated by splitting\n"
        "strictly across unseen persons/speakers and AI synthesis tools, NOT by random\n"
        "windows. Windows sampled from the same audio file are strongly correlated\n"
        "and NOT independent observations."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
