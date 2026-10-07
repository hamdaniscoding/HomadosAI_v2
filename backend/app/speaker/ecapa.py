"""ECAPA-TDNN speaker encoder with lazy loading. No fallback."""

from __future__ import annotations

import logging

import numpy as np

from app.config import get_settings

logger = logging.getLogger("homados.speaker.ecapa")


class EcapaEncoder:
    """SpeechBrain ECAPA-TDNN encoder (VoxCeleb pretrained)."""

    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._load_error: str | None = None

    @property
    def loaded(self) -> bool:
        """Whether the model is ready for inference."""
        return self._loaded

    @property
    def load_error(self) -> str | None:
        """Error message if loading failed."""
        return self._load_error

    def _ensure_loaded(self) -> None:
        """Lazily load the model on first use."""
        if self._loaded or self._load_error is not None:
            return
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier

            settings = get_settings()
            savedir = str(settings.ecapa_dir)
            settings.ecapa_dir.mkdir(parents=True, exist_ok=True)
            device = settings.torch_device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            elif device.startswith("cuda") and not torch.cuda.is_available():
                device = "cpu"
            self._model = EncoderClassifier.from_hparams(
                source=settings.ecapa_source,
                savedir=savedir,
                run_opts={"device": device},
            )
            self._loaded = True
            logger.info("ECAPA-TDNN loaded from %s", settings.ecapa_source)
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            logger.warning("ECAPA-TDNN not loaded: %s", exc)

    def embed(self, waveform: np.ndarray) -> list[float]:
        """Return a 192-dim L2-normalized embedding. Raises RuntimeError if not loaded."""
        self._ensure_loaded()
        if not self._loaded or self._model is None:
            raise RuntimeError(f"ECAPA encoder not available: {self._load_error}")

        import torch
        import torchaudio

        y = np.asarray(waveform, dtype=np.float32).flatten()
        wav = torch.from_numpy(y).unsqueeze(0)
        sr = get_settings().sample_rate
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        with torch.no_grad():
            emb = self._model.encode_batch(wav).squeeze().cpu().numpy()
        vec = np.asarray(emb, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two embedding vectors.

    Raises ValueError on dimension mismatch.
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    if va.shape != vb.shape:
        raise ValueError(
            f"Dimension mismatch: {va.shape} vs {vb.shape}"
        )
    if va.size == 0:
        raise ValueError("Empty embeddings")
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(va, vb) / denom, -1.0, 1.0))


_encoder: EcapaEncoder | None = None


def get_ecapa() -> EcapaEncoder:
    """Module-level singleton for the ECAPA encoder."""
    global _encoder
    if _encoder is None:
        _encoder = EcapaEncoder()
    return _encoder
