"""Tests for the PolyphonicGenerator module."""

import types
import importlib
import sys
from pathlib import Path
import pytest

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
MIN_OCTAVE = mg.MIN_OCTAVE
MAX_OCTAVE = mg.MAX_OCTAVE


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


def test_generate_invalid_octave_low():
    """Providing a base octave below ``MIN_OCTAVE`` should raise ``ValueError``."""

    gen = PolyphonicGenerator()
    with pytest.raises(ValueError):
        gen.generate("C", 4, ["C"], base_octaves={"soprano": MIN_OCTAVE - 1})


def test_generate_invalid_octave_high():
    """Providing a base octave above ``MAX_OCTAVE`` should raise ``ValueError``."""

    gen = PolyphonicGenerator()
    with pytest.raises(ValueError):
        gen.generate("C", 4, ["C"], base_octaves={"alto": MAX_OCTAVE + 1})


def test_generate_invalid_num_notes():
    """Non-positive ``num_notes`` should raise ``ValueError``."""

    gen = PolyphonicGenerator()
    with pytest.raises(ValueError):
        gen.generate("C", 0, ["C"])  # num_notes must be positive


def test_enforce_voice_leading_corrects_crossing_and_spacing():
    """Lower voices should never rise above higher ones after adjustment."""

    gen = PolyphonicGenerator()
    voices = {
        "soprano": ["C4"],
        "alto": ["E4"],
        "tenor": ["C3"],
        "bass": ["C2"],
    }
    gen._enforce_voice_leading(voices)

    mids = [note_to_midi(voices[v][0]) for v in gen.voices]
    assert mids == sorted(mids, reverse=True)
    assert voices["soprano"][0] == "C5"
    assert voices["tenor"][0] == "C4"


