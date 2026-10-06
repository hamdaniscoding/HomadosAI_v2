"""Tests for PCM conversion."""

from __future__ import annotations

import pytest

from app.core.audio import pcm16_to_float32


def test_pcm_conversion_odd_length():
    """Odd byte length raises ValueError."""
    with pytest.raises(ValueError, match="odd byte length"):
        pcm16_to_float32(b"\x00\x00\x00")


def test_pcm_conversion_valid():
    """Valid PCM bytes convert to float32 array."""
    result = pcm16_to_float32(b"\x00\x00\x00\x80")
    assert len(result) == 2
    assert result[0] == 0.0
    assert result[1] == -1.0
