import importlib
import sys
import types
from pathlib import Path

import pytest

# Stub minimal dependencies so the module imports without optional packages
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
stub_mido.MidiFile = object
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: object()
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

mod = importlib.import_module("melody_generator")
vl = importlib.import_module("melody_generator.voice_leading")
np = mod.np


def test_counterpoint_penalties_vectorized_matches_scalar():
    """Vectorized penalty helper should mirror scalar logic."""
    if np is None:
        pytest.skip("numpy not available")
    prev = "C4"
    cands = ["G4", "A4", "C5"]
    vec = vl.counterpoint_penalties(prev, cands, prev_dir=1, prev_interval=7)
    scalar = [vl.counterpoint_penalty(prev, c, prev_dir=1, prev_interval=7) for c in cands]
    assert pytest.approx(vec.tolist()) == scalar


def test_parallel_fifths_mask_matches_scalar():
    """Vectorized parallel motion detection should match scalar version."""
    if np is None:
        pytest.skip("numpy not available")
    prev_a = "C4"
    prev_b = "G3"
    curr_b = "D4"
    cands = ["A4", "B4", "C5"]
    mask = vl.parallel_fifths_mask(prev_a, prev_b, cands, curr_b)
    expected = [vl.parallel_fifth_or_octave(prev_a, prev_b, c, curr_b) for c in cands]
    assert mask.tolist() == expected


def test_pick_note_uses_numpy_choice(monkeypatch):
    """``pick_note`` should rely on ``numpy.random.choice`` when available."""
    if np is None:
        pytest.skip("numpy not available")
    called = {"flag": False}

    def fake_choice(seq, p=None):
        called["flag"] = True
        return seq[0]

    monkeypatch.setattr(mod.np.random, "choice", fake_choice)
    res = mod.pick_note(["A", "B"], [0.7, 0.3])
    assert res == "A"
    assert called["flag"]
