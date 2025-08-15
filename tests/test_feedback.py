"""Tests for the feedback and refinement helpers."""

import importlib
import sys
import types
from pathlib import Path
import random
import pytest

# Lightweight stubs injected via fixture so other tests remain unaffected.
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
stub_mido.MidiFile = object
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: object()
stub_mido.bpm2tempo = lambda bpm: bpm

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Provide stand-in modules required for import."""

    monkeypatch.setitem(sys.modules, "mido", stub_mido)
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)





def test_compute_fmd_matches_training():
    """Distance for the training set itself should be near zero."""

    fb = importlib.import_module("melody_generator.feedback")
    mg = importlib.import_module("melody_generator")
    pitches = fb.__dict__["_TRAINING_PITCHES"]
    notes = [mg.midi_to_note(p) for p in pitches]
    assert fb.compute_fmd(notes) < 1e-6


def test_refine_with_fmd_improves_distance():
    """Hill climbing should never worsen Frechet distance."""

    fb = importlib.import_module("melody_generator.feedback")
    random.seed(0)
    melody = ["C4"] * 8
    before = fb.compute_fmd(melody)
    refined = fb.refine_with_fmd(melody.copy(), "C", ["C"], 4, max_iter=1)
    after = fb.compute_fmd(refined)
    assert after <= before


def test_refine_with_fmd_short_sequences_return_input():
    """Sequences with fewer than three notes should not be modified."""

    fb = importlib.import_module("melody_generator.feedback")

    one = ["C4"]
    two = ["C4", "E4"]
    assert fb.refine_with_fmd(one.copy(), "C", ["C"], 4) == one
    assert fb.refine_with_fmd(two.copy(), "C", ["C"], 4) == two


def test_refine_with_fmd_raises_on_empty_chord_prog():
    """Empty chord progressions cannot guide note selection and should error."""

    fb = importlib.import_module("melody_generator.feedback")

    with pytest.raises(ValueError):
        fb.refine_with_fmd(["C4", "E4", "G4"], "C", [], 4)


def test_melody_stats_raises_on_empty_sequence():
    """_melody_stats should clearly reject empty input sequences.

    The function computes mean and variance of MIDI pitches and would otherwise
    divide by zero when no notes are supplied.  A descriptive ValueError ensures
    that callers are informed about the requirement for at least one note.
    """

    fb = importlib.import_module("melody_generator.feedback")

    # ``notes`` is empty, so the helper should raise a ValueError.
    with pytest.raises(ValueError, match="at least one note"):
        fb._melody_stats([])


def test_compute_fmd_raises_on_empty_sequence():
    """compute_fmd should propagate the empty-sequence validation."""

    fb = importlib.import_module("melody_generator.feedback")

    # The public API should also reject empty note lists to maintain consistency.
    with pytest.raises(ValueError, match="at least one note"):
        fb.compute_fmd([])

