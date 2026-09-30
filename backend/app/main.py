from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers.api import router as api_router
from app.services.status import engine_status

settings = get_settings()
ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(
    title="HOMADOS AI — VoiceGuardAI",
    description="Real-time voice-cloning impersonation detection for SIH 2026 PS 26104.",
    version="3.0.0",
)

origins = settings.origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/healthz")
def healthz():
    return engine_status()


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    images = FRONTEND_DIST / "images"
    if images.exists():
        app.mount("/images", StaticFiles(directory=images), name="images")

    RESERVED = {"docs", "redoc", "openapi.json", "healthz"}

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api") or full_path in RESERVED:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
