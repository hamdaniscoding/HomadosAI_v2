"""Pydantic models for HTTP and WebSocket messages."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- WebSocket client -> server ----------

class WsStartMessage(BaseModel):
    """First message the client must send to initiate a stream."""
    type: str = Field("start")
    sample_rate: int
    channels: int
    encoding: str
    mode: str
    save_session: bool = False


class WsStopMessage(BaseModel):
    """Client message to end the stream."""
    type: str = Field("stop")


# ---------- WebSocket server -> client ----------

class WsReadyMessage(BaseModel):
    """Sent once after a valid start message."""
    type: str = "ready"
    session_id: str
    window_seconds: float
    hop_seconds: float
    detector: str | None = None


class WsStatusMessage(BaseModel):
    """Progress update sent every 0.5 s of received audio."""
    type: str = "status"
    state: str = "listening"
    received_seconds: float
    speech_seconds: float | None = None
    needed_seconds: float


class SpeakerInfo(BaseModel):
    id: int
    speech_seconds: float
    ai_probability: float | None = None
    smoothed_probability: float | None = None
    reason: str | None = None


class WsResultMessage(BaseModel):
    """Inference result sent once per hop."""
    type: str = "result"
    seq: int
    t: float
    window_seconds: float
    ai_probability: float | None = None
    verdict: str | None = None
    smoothed_probability: float | None = None
    latency_ms: float | None = None
    detector: str | None = None
    reason: str | None = None
    speech_ratio: float | None = None
    active_speaker: int | None = None
    speakers: list[SpeakerInfo] | None = None


class WsErrorMessage(BaseModel):
    """Error message sent before closing the socket."""
    type: str = "error"
    code: str
    message: str


# ---------- HTTP responses ----------

class HealthResponse(BaseModel):
    """GET /api/v1/health response."""
    status: str = "ok"
    app_version: str
    python_version: str
    torch_version: str | None = None
    cuda_available: bool | None = None
    device: str
    sample_rate: int
    window_seconds: float
    hop_seconds: float
    calibrated: bool
    detectors: list[DetectorStatus] = Field(default_factory=list)
    ecapa: EcapaStatus
    last_inference_ms: float | None = None


class DetectorStatus(BaseModel):
    """Status of a single detector."""
    name: str
    loaded: bool
    load_error: str | None = None


class EcapaStatus(BaseModel):
    """Status of the ECAPA encoder."""
    loaded: bool
    load_error: str | None = None


class AnalyzeResponse(BaseModel):
    """POST /api/v1/analyze response."""
    filename: str
    duration_seconds: float
    sample_rate: int
    verdict: str | None = None
    reason: str | None = None


class EnrollResponse(BaseModel):
    """POST /api/v1/enroll response."""
    dim: int
    embedding: list[float]


# Rebuild forward refs for HealthResponse (DetectorStatus used before definition)
HealthResponse.model_rebuild()
