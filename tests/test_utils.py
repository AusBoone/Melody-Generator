"""Tests for shared helpers in :mod:`melody_generator.utils`.

This module exercises :func:`parse_chord_progression` which provides
consistent chord parsing and random progression behaviour for both the
command-line and web interfaces. The tests focus on canonicalisation,
random generation, error handling and fallback behaviour when users
leave the chord field blank.
"""

from __future__ import annotations

import importlib

import pytest

from melody_generator.utils import parse_chord_progression


@pytest.fixture()
def _patch_progression(monkeypatch):
    """Yield a helper for stubbing ``generate_random_chord_progression``.

    Each test can call the returned function with a stub implementation.
    The helper ensures the stub is installed on the ``melody_generator``
    package before invoking :func:`parse_chord_progression` so the lazy
    imports performed inside the helper pick up the patched behaviour.
    """

    module = importlib.import_module("melody_generator")

    def installer(func):
        monkeypatch.setattr(module, "generate_random_chord_progression", func)

    return installer


def test_parse_chord_progression_canonicalises_chords():
    """Manual progressions should be stripped and canonicalised."""

    result = parse_chord_progression("c, am , g", key="c", allow_empty=False)
    assert result == ["C", "Am", "G"]


def test_parse_chord_progression_random_count_uses_stub(_patch_progression):
    """Explicit ``random_count`` should call the stub with the same value."""

    calls: list[tuple[str, int]] = []

    def fake_progression(key: str, length: int = 4) -> list[str]:
        # Record the canonical key and requested length for later assertions.
        calls.append((key, length))
        return [f"{key}:{length}"] * length

    _patch_progression(fake_progression)
    chords = parse_chord_progression(None, key="c", random_count=3)

    assert chords == ["C:3"] * 3
    assert calls == [("C", 3)]


def test_parse_chord_progression_rejects_non_positive_random_count():
    """Zero or negative ``random_count`` should raise ``ValueError``."""

    with pytest.raises(ValueError) as excinfo:
        parse_chord_progression(None, key="C", random_count=0)
    assert "Random chord count" in str(excinfo.value)


def test_parse_chord_progression_falls_back_when_empty(_patch_progression):
    """Empty strings should trigger random generation when allowed."""

    captured: list[tuple[str, int]] = []

    def fake_progression(key: str, length: int = 4) -> list[str]:
        # Capture the parameters to verify canonical key handling and default
        # length usage when the caller omits chords entirely.
        captured.append((key, length))
        return ["FALLBACK"]

    _patch_progression(fake_progression)
    chords = parse_chord_progression("   ", key="d", allow_empty=True)

    assert chords == ["FALLBACK"]
    assert captured == [("D", 4)]


def test_parse_chord_progression_invalid_chord_reports_name():
    """Unknown chord names should surface in the error message."""

    with pytest.raises(ValueError) as excinfo:
        parse_chord_progression("C, H", key="C", allow_empty=False)

    message = str(excinfo.value)
    assert "Unknown chord" in message
    assert "H" in message
