"""Unit tests for the random rhythm helper."""

import importlib
import sys
import types
from pathlib import Path

# Stub out optional dependencies so ``melody_generator`` imports cleanly.
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *a, **k: None
stub_mido.MidiFile = lambda *a, **k: None
stub_mido.MidiTrack = lambda *a, **k: []
stub_mido.MetaMessage = lambda *a, **k: None
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

melody_generator = importlib.import_module("melody_generator")


def test_generate_random_rhythm_pattern_valid_lengths():
    """The helper returns the requested number of durations from the allowed set."""
    length = 6
    pattern = melody_generator.generate_random_rhythm_pattern(length)
    allowed = {0.25, 0.5, 0.75, 0.125, 0.0625, 0}
    assert len(pattern) == length
    assert all(val in allowed for val in pattern)
