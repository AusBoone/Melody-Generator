"""Unit tests for the rhythm generation engine."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rhythm = importlib.import_module("melody_generator.rhythm_engine")


def test_generate_rhythm_length():
    """``generate_rhythm`` should return the requested number of durations."""
    pattern = rhythm.generate_rhythm(5)
    assert len(pattern) == 5


def test_rhythm_generator_custom_transitions():
    """A custom ``RhythmGenerator`` should honour its transition map."""

    gen = rhythm.RhythmGenerator({0.5: {0.5: 1.0}}, start=0.5)
    assert gen.generate(3) == [0.5, 0.5, 0.5]


def test_generate_uses_numpy_choice(monkeypatch):
    """``RhythmGenerator.generate`` should call ``numpy.random.choice`` when available."""
    if rhythm.np is None:
        pytest.skip("numpy not available")

    called = {"flag": False}

    def fake_choice(seq, p=None):
        called["flag"] = True
        return seq[0]

    monkeypatch.setattr(rhythm.np.random, "choice", fake_choice)
    gen = rhythm.RhythmGenerator(start=0.25)
    gen.generate(2)
    assert called["flag"]

