"""Unified device resolution and GPU policy."""

from __future__ import annotations

import logging
from typing import Any
import torch

logger = logging.getLogger("homados.device")


def resolve_device(requested: str = "auto") -> torch.device:
    """Resolve device string to torch.device.

    - "auto": cuda if available AND a tiny CUDA op succeeds, else cpu.
    - "cuda" / "cuda:X": require CUDA with clear error if not available or op fails.
    - "cpu": force cpu.
    """
    req = (requested or "auto").strip().lower()

    if req == "auto":
        if torch.cuda.is_available():
            try:
                # Test a tiny CUDA operation
                test_tensor = torch.zeros(1, device="cuda")
                del test_tensor
                return torch.device("cuda")
            except Exception as exc:
                logger.warning(
                    "CUDA available but sanity allocation failed (%s); falling back to CPU.",
                    exc,
                )
                return torch.device("cpu")
        return torch.device("cpu")

    if req == "cpu":
        return torch.device("cpu")

    if req.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError(
                f"Requested device '{requested}', but CUDA is not available on this system "
                f"(torch.cuda.is_available() is False, torch version {torch.__version__})."
            )
        try:
            test_tensor = torch.zeros(1, device=req)
            del test_tensor
            return torch.device(req)
        except Exception as exc:
            raise RuntimeError(
                f"Requested CUDA device '{requested}' failed sanity check operation: {exc}"
            ) from exc

    # Try parsing other device strings (e.g. mps)
    try:
        return torch.device(req)
    except Exception as exc:
        raise ValueError(f"Unsupported device '{requested}': {exc}") from exc


def get_gpu_info() -> dict[str, Any]:
    """Return GPU hardware details or None values if running on CPU."""
    info: dict[str, Any] = {
        "gpu_name": None,
        "vram_mb": None,
        "cuda_version": getattr(torch.version, "cuda", None),
    }
    if torch.cuda.is_available():
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_mb"] = round(props.total_memory / (1024 * 1024), 2)
        except Exception as exc:
            logger.debug("Could not read GPU properties: %s", exc)
    return info
