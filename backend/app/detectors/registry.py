"""Detector registry: register, list, and retrieve active detectors."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.detectors.base import Detector

logger = logging.getLogger("homados.detectors.registry")


@dataclass
class _DetectorEntry:
    """Internal record for a registered detector."""
    detector: Detector
    loaded: bool = False
    load_error: str | None = None


_registry: dict[str, _DetectorEntry] = {}


def register(detector: Detector) -> None:
    """Register a detector and attempt to load it."""
    entry = _DetectorEntry(detector=detector)
    try:
        detector.load()
        entry.loaded = True
        logger.info("Detector '%s' loaded successfully.", detector.name)
    except Exception as exc:
        entry.load_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Detector '%s' failed to load: %s", detector.name, exc)
    _registry[detector.name] = entry


def unregister(name: str) -> None:
    """Remove a detector from the registry."""
    _registry.pop(name, None)


def list_detectors() -> list[dict[str, object]]:
    """Return status of all registered detectors."""
    return [
        {
            "name": name,
            "loaded": entry.loaded,
            "load_error": entry.load_error,
        }
        for name, entry in _registry.items()
    ]


def get_active() -> Detector | None:
    """Return the first successfully loaded detector, or None."""
    for entry in _registry.values():
        if entry.loaded:
            return entry.detector
    return None
