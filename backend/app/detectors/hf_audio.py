"""Hugging Face transformers audio classification detector adapter."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

from app.detectors.base import Detector

logger = logging.getLogger("homados.detectors.hf_audio")


class HFAudioDetector:
    """Detector adapter for Hugging Face audio classification models.

    Conforms to the Detector protocol. Loads any Hugging Face model supporting
    AutoModelForAudioClassification (e.g., wav2vec2, Hubert, WavLM backbone with
    a sequence classification head).
    """

    def __init__(
        self,
        model_id: str | Path,
        fake_label: str | int,
        device: str | None = None,
        window_seconds: float = 5.0,
    ) -> None:
        if fake_label is None or (isinstance(fake_label, str) and not fake_label.strip()):
            raise ValueError(
                "fake_label is required and cannot be empty (no default guessing)."
            )

        self.model_id = str(model_id)
        self.fake_label = fake_label
        self._window_seconds = float(window_seconds)

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.feature_extractor: Any = None
        self.model: Any = None
        self._fake_class_id: int | None = None
        self._use_fp16: bool = False

    @property
    def name(self) -> str:
        return f"hf_audio:{self.model_id}"

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    def _resolve_fake_label(self, id2label: dict[Any, Any] | None) -> int:
        """Resolve fake_label against the model's id2label config.

        Refuses to load if fake_label is not found (no silent fallback).
        """
        if not id2label:
            raise ValueError(
                f"Model config for '{self.model_id}' does not provide an id2label mapping; "
                f"cannot verify fake_label='{self.fake_label}'."
            )

        # Normalize keys to int and values to str
        normalized: dict[int, str] = {int(k): str(v) for k, v in id2label.items()}
        name_to_id: dict[str, int] = {str(v): int(k) for k, v in id2label.items()}

        if isinstance(self.fake_label, int):
            if self.fake_label in normalized:
                return self.fake_label
            raise ValueError(
                f"fake_label class index {self.fake_label} not found in model id2label: "
                f"{normalized} (no silent fallback)."
            )

        # fake_label is a string
        if self.fake_label in name_to_id:
            return name_to_id[self.fake_label]

        # Check if the string is numeric index
        if self.fake_label.isdigit() and int(self.fake_label) in normalized:
            return int(self.fake_label)

        raise ValueError(
            f"fake_label '{self.fake_label}' not found in model id2label: "
            f"{normalized} (no silent fallback)."
        )

    def load(self) -> None:
        """Load feature extractor and model weights, verifying fake_label."""
        logger.info("Loading HFAudioDetector from '%s' on %s...", self.model_id, self.device)
        target_path = self.model_id
        if not Path(target_path).exists():
            slug = str(self.model_id).replace("/", "--")
            cached_cand = Path("models/hf_cache") / slug
            if cached_cand.exists():
                target_path = str(cached_cand)
            elif (Path("models/hf_cache") / Path(self.model_id).name).exists():
                target_path = str(Path("models/hf_cache") / Path(self.model_id).name)

        self.feature_extractor = AutoFeatureExtractor.from_pretrained(target_path)
        self.model = AutoModelForAudioClassification.from_pretrained(
            target_path,
            use_safetensors=True,
        )

        # Verify fake_label exists in config id2label
        raw_id2label = getattr(self.model.config, "id2label", None)
        self._fake_class_id = self._resolve_fake_label(raw_id2label)
        logger.info(
            "Resolved fake_label '%s' to class index %d for model '%s'.",
            self.fake_label,
            self._fake_class_id,
            self.model_id,
        )

        self.model.to(self.device)
        self.model.eval()

        # Sanity check FP16 against FP32 on CUDA
        self._use_fp16 = False
        if self.device.type == "cuda":
            self._evaluate_fp16_sanity()

    def _evaluate_fp16_sanity(self) -> None:
        """Check if fp16 matches fp32 on the same input on CUDA."""
        try:
            n_samples = int(self.sample_rate * self.window_seconds)
            test_waveform = np.sin(np.linspace(0, 100 * np.pi, n_samples), dtype=np.float32) * 0.1
            p_fp32 = self._predict_waveform_raw(test_waveform, use_fp16=False)

            self.model.half()
            p_fp16 = self._predict_waveform_raw(test_waveform, use_fp16=True)

            if math.isfinite(p_fp16) and abs(p_fp16 - p_fp32) < 0.05:
                self._use_fp16 = True
                logger.info(
                    "CUDA FP16 sanity check passed (p_fp32=%.4f, p_fp16=%.4f). Using FP16.",
                    p_fp32,
                    p_fp16,
                )
            else:
                self._use_fp16 = False
                self.model.float()
                logger.warning(
                    "CUDA FP16 sanity check failed (p_fp32=%.4f, p_fp16=%.4f). Falling back to FP32.",
                    p_fp32,
                    p_fp16,
                )
        except Exception as exc:
            self._use_fp16 = False
            self.model.float()
            logger.warning("CUDA FP16 sanity check encountered error (%s). Falling back to FP32.", exc)

    def _predict_waveform_raw(self, waveform: np.ndarray, use_fp16: bool = False) -> float:
        """Internal inference runner."""
        assert self.feature_extractor is not None
        assert self.model is not None
        assert self._fake_class_id is not None

        inputs = self.feature_extractor(
            waveform,
            sampling_rate=self.sample_rate,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        if use_fp16 and self.device.type == "cuda":
            inputs = {k: v.half() if v.dtype == torch.float32 else v for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            fake_prob = probs[0, self._fake_class_id].item()

        return float(fake_prob)

    def predict(self, waveform: np.ndarray, sample_rate: int | None = None) -> float:
        """Return the softmax probability of the fake class as a float [0, 1].

        Raises ValueError on wrong sample rate or empty input.
        """
        if waveform is None:
            raise ValueError("Waveform cannot be None.")

        if not isinstance(waveform, np.ndarray):
            try:
                waveform = np.asarray(waveform, dtype=np.float32)
            except Exception as exc:
                raise ValueError(f"Invalid waveform input type: {type(waveform)}") from exc

        if waveform.size == 0:
            raise ValueError("Waveform cannot be empty (0 samples).")

        if sample_rate is not None and sample_rate != self.sample_rate:
            raise ValueError(
                f"Wrong sample rate: expected {self.sample_rate} Hz, got {sample_rate} Hz."
            )

        # Handle 2D inputs (channels, time) or (1, time)
        if waveform.ndim == 2:
            if waveform.shape[0] == 1:
                waveform = waveform.squeeze(0)
            elif waveform.shape[1] == 1:
                waveform = waveform.squeeze(1)
            else:
                waveform = waveform.mean(axis=0)
        elif waveform.ndim > 2:
            raise ValueError(f"Expected 1D audio waveform, got shape {waveform.shape}")

        waveform = waveform.astype(np.float32, copy=False)

        if not np.isfinite(waveform).all():
            raise ValueError("Waveform contains NaN or Inf values.")

        if self.model is None or self.feature_extractor is None:
            self.load()

        prob = self._predict_waveform_raw(waveform, use_fp16=self._use_fp16)
        if math.isnan(prob) or math.isinf(prob):
            # Fall back to FP32 if FP16 generated NaN/Inf
            if self._use_fp16:
                logger.warning("FP16 produced NaN/Inf; re-evaluating in FP32.")
                self.model.float()
                self._use_fp16 = False
                prob = self._predict_waveform_raw(waveform, use_fp16=False)
            if math.isnan(prob) or math.isinf(prob):
                raise RuntimeError("Model produced NaN or Inf probabilities.")

        return float(np.clip(prob, 0.0, 1.0))
