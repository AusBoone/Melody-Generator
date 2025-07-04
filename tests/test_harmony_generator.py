"""Tests for the chord progression helper."""

import importlib
import sys
from pathlib import Path
import types
import pytest

# Stub optional GUI/MIDI libs so the package imports cleanly.
stub_mido = types.ModuleType("mido")


class DummyMidiFile:
    """Lightweight stand-in used by ``create_midi_file`` during tests."""

    last_instance = None

    def __init__(self, *args, **kwargs) -> None:
        self.tracks = []
        DummyMidiFile.last_instance = self

    def save(self, _path: str) -> None:
        pass




class DummyMidiTrack(list):
    """Simple list subclass used to collect MIDI messages."""


class DummyMessage:
    """Minimal MIDI message holding only relevant attributes."""

    def __init__(self, type: str, **kwargs) -> None:
        self.type = type
        self.time = kwargs.get("time", 0)
        self.note = kwargs.get("note")
        self.velocity = kwargs.get("velocity")
        self.program = kwargs.get("program")


stub_mido.Message = DummyMessage
stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = DummyMidiTrack
stub_mido.MetaMessage = lambda *args, **kwargs: DummyMessage("meta", **kwargs)
stub_mido.bpm2tempo = lambda bpm: bpm

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")

# Ensure the repository root is on ``sys.path`` so the package imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Inject light-weight stubs for optional dependencies."""

    monkeypatch.setitem(sys.modules, "mido", stub_mido)
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

def test_generate_progression_lengths():
    """Progression generator returns chords and rhythm of requested length."""
    harmony = importlib.import_module("melody_generator.harmony_generator")
    chords, rhythm = harmony.generate_progression("C", length=4)
    assert len(chords) == 4
    assert len(rhythm) == 4
