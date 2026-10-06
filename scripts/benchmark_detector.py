#!/usr/bin/env python3
"""Speed benchmark script for audio classification detectors.

Measures inference latency and resource consumption on a standardized
5-second 16 kHz audio window.
NOTE: This script measures speed and hardware resource usage only, NOT detection accuracy.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import torch

# Ensure backend/ is in sys.path for app imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.detectors.hf_audio import HFAudioDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark latency and memory consumption of an audio detector. Speed only, not accuracy."
    )
    parser.add_argument(
        "--model-id",
        type=str,
        required=True,
        help="Hugging Face hub ID or local model directory path.",
    )
    parser.add_argument(
        "--fake-label",
        type=str,
        required=True,
        help="Label name or class index representing fake/spoof.",
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "cuda"],
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to run inference on ('cpu' or 'cuda').",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=30,
        help="Number of timed benchmark iterations (default: 30).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of untimed warmup iterations (default: 5).",
    )
    return parser.parse_args()


def run_benchmark(
    model_id: str,
    fake_label: str,
    device: str,
    runs: int,
    warmup: int,
) -> None:
    is_cuda = device == "cuda"
    if is_cuda and not torch.cuda.is_available():
        print("ERROR: CUDA requested but torch.cuda.is_available() is False.", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("HOMADOS AI - DETECTOR SPEED BENCHMARK")
    print("NOTICE: This benchmark measures speed only, not accuracy.")
    print("=" * 70)
    print(f"Model ID:    {model_id}")
    print(f"Fake label:  {fake_label}")
    print(f"Device:      {device.upper()}" + (f" ({torch.cuda.get_device_name(0)})" if is_cuda else ""))
    print(f"Runs:        {runs} iterations")
    print(f"Warmup:      {warmup} iterations")
    print("-" * 70)

    # Convert numeric string to int if applicable
    parsed_fake_label: str | int = int(fake_label) if fake_label.isdigit() else fake_label

    detector = HFAudioDetector(
        model_id=model_id,
        fake_label=parsed_fake_label,
        device=device,
        window_seconds=5.0,
    )

    if is_cuda:
        torch.cuda.reset_peak_memory_stats()

    print("Loading model and feature extractor...")
    load_start = time.perf_counter()
    detector.load()
    if is_cuda:
        torch.cuda.synchronize()
    load_time_s = time.perf_counter() - load_start
    print(f"Loaded in {load_time_s:.2f} s. FP16 enabled: {detector._use_fp16}")

    # Parameter count
    param_count = sum(p.numel() for p in detector.model.parameters())

    # Generate a realistic 5-second 16 kHz window
    n_samples = int(detector.sample_rate * detector.window_seconds)
    np.random.seed(42)
    waveform = (np.random.randn(n_samples).astype(np.float32) * 0.05)

    # Warmup
    if warmup > 0:
        print(f"Executing {warmup} warmup iterations...")
        for _ in range(warmup):
            _ = detector.predict(waveform)
        if is_cuda:
            torch.cuda.synchronize()

    # Timed runs
    print(f"Executing {runs} timed iterations...")
    latencies_ms: list[float] = []

    for _ in range(runs):
        if is_cuda:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = detector.predict(waveform)
        if is_cuda:
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    # Latency statistics
    median_latency = float(np.median(latencies_ms))
    p95_latency = float(np.percentile(latencies_ms, 95))
    max_latency = float(np.max(latencies_ms))
    min_latency = float(np.min(latencies_ms))

    # GPU memory
    gpu_peak_mb = (
        torch.cuda.max_memory_allocated() / (1024 ** 2) if is_cuda else 0.0
    )

    print("-" * 70)
    print("BENCHMARK RESULTS (SPEED ONLY):")
    print(f"  Parameter Count:     {param_count:,} ({param_count / 1e6:.2f} M)")
    print(f"  GPU Memory Peak:     {gpu_peak_mb:.2f} MB" if is_cuda else "  GPU Memory:          N/A (CPU)")
    print(f"  Min Latency:         {min_latency:.2f} ms")
    print(f"  Median Latency:      {median_latency:.2f} ms")
    print(f"  P95 Latency:         {p95_latency:.2f} ms")
    print(f"  Max Latency:         {max_latency:.2f} ms")
    print("=" * 70)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    run_benchmark(
        model_id=args.model_id,
        fake_label=args.fake_label,
        device=args.device,
        runs=args.runs,
        warmup=args.warmup,
    )


if __name__ == "__main__":
    main()
