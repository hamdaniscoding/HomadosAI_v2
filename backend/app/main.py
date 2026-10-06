"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

from app.api.http import router as http_router
from app.api.ws import router as ws_router
from app.config import get_settings

settings = get_settings()
ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"


def init_detector() -> None:
    """Register HFAudioDetector on app startup if DETECTOR_MODEL_ID is set."""
    current_settings = get_settings()
    if current_settings.detector_model_id:
        from app.detectors import registry
        from app.detectors.hf_audio import HFAudioDetector

        detector = HFAudioDetector(
            model_id=current_settings.detector_model_id,
            fake_label=current_settings.detector_fake_label,
            device=current_settings.torch_device if current_settings.torch_device else None,
            window_seconds=current_settings.window_seconds,
        )
        registry.register(detector)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_detector()
    yield


app = FastAPI(
    title="HOMADOS AI — VoiceGuardAI",
    description="Real-time AI voice detection backend.",
    version="0.1.0",
    lifespan=lifespan,
)

origins = settings.origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(http_router)
app.include_router(ws_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Lightweight health check for Docker / Render."""
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    images = FRONTEND_DIST / "images"
    if images.exists():
        app.mount("/images", StaticFiles(directory=images), name="images")

    RESERVED = {"docs", "redoc", "openapi.json", "healthz"}

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        """Serve the frontend SPA, avoiding API and doc routes."""
        if full_path.startswith("api") or full_path in RESERVED:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
