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

    from pydantic import model_validator

    @model_validator(mode="after")
    def validate_thresholds(self) -> Settings:
        """Validate that HUMAN < AI when both thresholds are set."""
        if self.verdict_human_threshold is not None and self.verdict_ai_threshold is not None:
            if self.verdict_human_threshold >= self.verdict_ai_threshold:
                raise ValueError(
                    f"Invalid threshold order: VERDICT_HUMAN_THRESHOLD ({self.verdict_human_threshold}) "
                    f"must be less than VERDICT_AI_THRESHOLD ({self.verdict_ai_threshold})."
                )
        return self

    app_env: str = "development"
    cors_origins: str = "*"
    window_seconds: float = 5.0
    hop_seconds: float = 1.0
    sample_rate: int = 16000
    max_session_seconds: int = 3600
    max_frame_bytes: int = 64000
    torch_device: str = "auto"
    ecapa_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    ecapa_savedir: str = "models/ecapa_tdnn"
    detector_model_id: str | None = None
    detector_fake_label: str | None = None
    min_speech_ratio: float = 0.5
    smoothing_window: int = 5
    verdict_ai_threshold: float | None = None
    verdict_human_threshold: float | None = None
    session_log_enabled: bool = True
    session_db_path: str = "data/sessions.db"

    @property
    def DETECTOR_MODEL_ID(self) -> str | None:
        """Alias for detector_model_id."""
        return self.detector_model_id

    @property
    def DETECTOR_FAKE_LABEL(self) -> str | None:
        """Alias for detector_fake_label."""
        return self.detector_fake_label

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
