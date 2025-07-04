"""Unit tests for the rhythm generation engine."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rhythm = importlib.import_module("melody_generator.rhythm_engine")


def test_generate_rhythm_length():
    """``generate_rhythm`` should return the requested number of durations."""
    pattern = rhythm.generate_rhythm(5)
    assert len(pattern) == 5
