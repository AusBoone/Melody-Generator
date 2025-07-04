"""Tests for basic voice leading constraints."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

vl = importlib.import_module("melody_generator.voice_leading")


def test_parallel_fifth_detection():
    """``parallel_fifth_or_octave`` identifies parallel motion."""
    assert vl.parallel_fifth_or_octave("C4", "E4", "G4", "B4") is False
    assert vl.parallel_fifth_or_octave("C4", "G4", "D4", "A4")


def test_counterpoint_penalty_parallel_and_contrary():
    """Penalty decreases weight for parallel fifths and rewards contrary motion."""

    # Previous interval was an ascending fifth
    penalty = vl.counterpoint_penalty(
        "G4",
        "D5",
        prev_dir=1,
        prev_interval=7,
    )
    assert penalty < 0

    # Now test contrary motion reward
    penalty = vl.counterpoint_penalty(
        "G4",
        "E4",
        prev_dir=1,
        prev_interval=5,
    )
    assert penalty > 0
