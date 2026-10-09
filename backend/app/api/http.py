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
        device=(
            ("cuda" if cuda_available else "cpu")
            if settings.torch_device == "auto"
            else settings.torch_device
        ),
        sample_rate=settings.sample_rate,
        window_seconds=settings.window_seconds,
        hop_seconds=settings.hop_seconds,
        calibrated=settings.verdict_ai_threshold is not None and settings.verdict_human_threshold is not None,
        detectors=[
            DetectorStatus(**d) for d in list_detectors()
        ],
        ecapa=EcapaStatus(
            loaded=ecapa.loaded,
            load_error=ecapa.load_error,
        ),
        last_inference_ms=_last_inference_ms,
    ).model_dump()


from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    save_session: bool = Form(False),
    source_name: str = Form(None)
) -> dict[str, Any]:
    """Upload an audio file for analysis."""
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "File exceeds 25 MB limit"})
    if not data:
        raise HTTPException(status_code=400, detail={"code": "empty_file", "message": "Empty audio upload"})

    filename = file.filename or "clip.wav"
    src_name = source_name or filename
    
    try:
        waveform, duration = decode_upload(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "decode_error", "message": str(exc)}) from exc

    settings = get_settings()
    if duration > settings.max_session_seconds:
        raise HTTPException(status_code=413, detail={"code": "duration_exceeded", "message": f"Audio duration {duration:.1f}s exceeds limit {settings.max_session_seconds}s"})

    from app.core.jobs import job_manager
    try:
        res = job_manager.create_job(waveform, save_session, src_name)
        return res
    except ValueError as exc:
        raise HTTPException(status_code=429, detail={"code": "busy", "message": str(exc)})

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, since: int = 0) -> dict[str, Any]:
    from app.core.jobs import job_manager
    job = job_manager.get_job(job_id, since)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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

@router.get("/sessions")
def list_sessions(limit: int = 50) -> dict[str, Any]:
    from app.core.db import get_db_logger
    db = get_db_logger()
    return {"sessions": db.get_latest_sessions(limit=limit)}

@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    from app.core.db import get_db_logger
    db = get_db_logger()
    session_data = db.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data


@router.get("/sessions/{session_id}/export.csv")
def export_session_csv(session_id: str) -> Any:
    from fastapi.responses import PlainTextResponse
    from app.core.db import get_db_logger
    import csv
    import io
    
    db = get_db_logger()
    session_data = db.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["seq", "t", "speech_ratio", "ai_probability", "smoothed_probability", "verdict", "latency_ms", "reason"])
    
    for r in session_data["results"]:
        writer.writerow([
            r.get("seq"), r.get("t"), r.get("speech_ratio"), 
            r.get("ai_probability"), r.get("smoothed_probability"),
            r.get("verdict"), r.get("latency_ms"), r.get("reason")
        ])
        
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=session_{session_id}.csv"
    })

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    from app.core.db import get_db_logger
    db = get_db_logger()
    import sqlite3
    try:
        with sqlite3.connect(db.db_path) as conn:
            # Check if exists
            row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.execute("DELETE FROM results WHERE session_id = ?", (session_id,))
            conn.commit()
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Database error")
    return {"status": "deleted"}
