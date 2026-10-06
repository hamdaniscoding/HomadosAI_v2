"""HTTP endpoints for health, analyze, and enroll."""

from __future__ import annotations

import sys
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app import __version__
from app.config import get_settings
from app.core.audio import decode_upload
from app.detectors.registry import get_active, list_detectors
from app.schemas import (
    AnalyzeResponse,
    DetectorStatus,
    EcapaStatus,
    EnrollResponse,
    HealthResponse,
)
from app.speaker.ecapa import get_ecapa

router = APIRouter(prefix="/api/v1")

_last_inference_ms: float | None = None


def set_last_inference_ms(ms: float) -> None:
    """Called by the WS handler to record the most recent inference latency."""
    global _last_inference_ms
    _last_inference_ms = ms


@router.get("/health")
def health() -> dict[str, Any]:
    """Return real system status. Only measured values."""
    torch_version: str | None = None
    cuda_available: bool | None = None
    try:
        import torch
        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
    except ImportError:
        pass

    settings = get_settings()
    ecapa = get_ecapa()

    return HealthResponse(
        app_version=__version__,
        python_version=sys.version,
        torch_version=torch_version,
        cuda_available=cuda_available,
        device=settings.torch_device,
        detectors=[
            DetectorStatus(**d) for d in list_detectors()
        ],
        ecapa=EcapaStatus(
            loaded=ecapa.loaded,
            load_error=ecapa.load_error,
        ),
        last_inference_ms=_last_inference_ms,
    ).model_dump()


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload an audio file for analysis."""
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    filename = file.filename or "clip.wav"
    try:
        waveform, duration = decode_upload(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detector = get_active()
    if detector is None:
        return AnalyzeResponse(
            filename=filename,
            duration_seconds=round(duration, 3),
            sample_rate=get_settings().sample_rate,
            verdict=None,
            reason="no_detector_loaded",
        ).model_dump()

    import time
    t0 = time.perf_counter()
    ai_prob = detector.predict(waveform)
    latency = (time.perf_counter() - t0) * 1000
    set_last_inference_ms(latency)

    return AnalyzeResponse(
        filename=filename,
        duration_seconds=round(duration, 3),
        sample_rate=get_settings().sample_rate,
        verdict=None,
        reason="thresholds_not_calibrated",
    ).model_dump()


@router.post("/enroll")
async def enroll(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload audio to get an ECAPA speaker embedding."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    filename = file.filename or "enroll.wav"
    try:
        waveform, _ = decode_upload(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ecapa = get_ecapa()
    if ecapa.load_error is not None:
        raise HTTPException(
            status_code=503,
            detail=f"ECAPA encoder not available: {ecapa.load_error}",
        )
    try:
        embedding = ecapa.embed(waveform)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return EnrollResponse(
        dim=len(embedding),
        embedding=embedding,
    ).model_dump()
