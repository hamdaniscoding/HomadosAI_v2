from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    cors_origins: str = "*"
    window_seconds: float = 5.0
    hop_seconds: float = 1.0
    sample_rate: int = 16000
    max_session_seconds: int = 3600
    max_frame_bytes: int = 64000
    torch_device: str = "cpu"
    ecapa_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    ecapa_savedir: str = "models/ecapa_tdnn"

    @property
    def origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def ecapa_dir(self) -> Path:
        """Absolute path to the ECAPA model directory."""
        return (ROOT / self.ecapa_savedir).resolve()


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
