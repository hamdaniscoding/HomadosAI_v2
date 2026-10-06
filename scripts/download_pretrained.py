#!/usr/bin/env python3
"""Download public pretrained weights for HOMADOS AI.

ECAPA-TDNN (SpeechBrain, VoxCeleb1+2) for speaker embedding inference.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ECAPA_DIR = ROOT / "models" / "ecapa_tdnn"


def download_ecapa() -> None:
    """Fetch the SpeechBrain ECAPA-TDNN pretrained checkpoint."""
    ECAPA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError:
        print("Install ML extras first: pip install -r backend/requirements-ml.txt")
        print("Python 3.10-3.12 is recommended for PyTorch + SpeechBrain.")
        sys.exit(1)

    print("Fetching speechbrain/spkrec-ecapa-voxceleb into", ECAPA_DIR)
    EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(ECAPA_DIR),
        run_opts={"device": "cpu"},
    )
    print("ECAPA-TDNN pretrained checkpoint is ready (inference only).")


if __name__ == "__main__":
    if "--ecapa" in sys.argv or "--all" in sys.argv:
        download_ecapa()
    else:
        print("Run with --ecapa after installing backend/requirements-ml.txt")
