"""Tests for the PolyphonicGenerator module."""

import types
import importlib
import sys
from pathlib import Path

# Stub 'mido' so ``PolyphonicGenerator.to_midi`` works without the real package.
stub_mido = types.ModuleType("mido")

class DummyMessage:
    """Lightweight MIDI message used in tests."""

    def __init__(self, type: str, **kw) -> None:
        self.type = type
        self.time = kw.get("time", 0)
        self.note = kw.get("note")
        self.velocity = kw.get("velocity")
        self.program = kw.get("program")

class DummyMidiFile:
    """Record MIDI tracks written during tests."""

    last_instance = None

    def __init__(self, *a, **kw) -> None:
        self.tracks = []
        DummyMidiFile.last_instance = self

    def save(self, _p: str) -> None:  # pragma: no cover - no disk IO needed
        pass

class DummyMidiTrack(list):
    pass

stub_mido.Message = DummyMessage
stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = DummyMidiTrack
stub_mido.MetaMessage = lambda *a, **kw: DummyMessage("meta", **kw)
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules["mido"] = stub_mido

# Minimal Tk stub so ``melody_generator`` imports without GUI libs.
tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

polyphony = importlib.import_module("melody_generator.polyphony")
mg = importlib.import_module("melody_generator")
PolyphonicGenerator = polyphony.PolyphonicGenerator
note_to_midi = mg.note_to_midi
MidiFileStub = mg.MidiFile


def test_generate_returns_all_voices():
    """All four voices should be produced and ordered correctly."""
    gen = PolyphonicGenerator()
    parts = gen.generate("C", 4, ["C", "G"])
    assert set(parts) == {"soprano", "alto", "tenor", "bass"}
    for voice in gen.voices:
        assert len(parts[voice]) == 4
    # Verify no voice crossing occurs after adjustment
    for quartet in zip(parts["soprano"], parts["alto"], parts["tenor"], parts["bass"]):
        mids = [note_to_midi(n) for n in quartet]
        assert mids == sorted(mids, reverse=True)


