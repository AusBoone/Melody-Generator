"""Tests for the chord progression helper."""

import importlib
import sys
from pathlib import Path
import types
import pytest
import random

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
    # Use lowercase key to ensure canonicalisation works transparently.
    chords, rhythm = harmony.generate_progression("c", length=4)
    assert len(chords) == 4
    assert len(rhythm) == 4


def test_degree_to_chord_diminished():
    """Scale degrees resolving to diminished triads retain the ``dim`` tag."""

    harmony = importlib.import_module("melody_generator.harmony_generator")
    # In C major the leading tone (degree seven) forms a B diminished triad.
    # Pass the key in lowercase to verify case-insensitive handling.
    chord = harmony._degree_to_chord("c", 6)
    assert chord == "Bdim"


def test_generate_progression_canonicalizes_key():
    """Lowercase keys should yield the same results as uppercase keys."""

    harmony = importlib.import_module("melody_generator.harmony_generator")
    random.seed(0)
    chords_upper, rhythm_upper = harmony.generate_progression("C", length=4)
    random.seed(0)
    chords_lower, rhythm_lower = harmony.generate_progression("c", length=4)
    assert chords_upper == chords_lower
    assert rhythm_upper == rhythm_lower


def test_harmony_generator_rule_based():
    """Fallback generator should match bar count when no model is supplied."""
    harmony = importlib.import_module("melody_generator.harmony_generator")
    gen = harmony.HarmonyGenerator()
    rhythm = [1.0] * 4  # one bar of 4/4
    chords, durations = gen.generate("C", ["C4"], rhythm)
    assert len(chords) == 1
    assert durations == [4]


def test_harmony_generator_multiple_bars():
    """Downbeat detection should produce one chord per bar."""
    harmony = importlib.import_module("melody_generator.harmony_generator")
    gen = harmony.HarmonyGenerator()
    rhythm = [1.0] * 8  # two bars of 4/4
    chords, durations = gen.generate("C", ["C4"], rhythm)
    assert len(chords) == 2
    assert durations == [4, 4]


def test_harmony_generator_custom_model():
    """A provided model should be queried once per bar."""
    harmony = importlib.import_module("melody_generator.harmony_generator")

    class DummyModel:
        def __init__(self):
            self.calls = 0

        def predict(self, history):
            self.calls += 1
            # Always return the first degree as most likely
            return [1.0] + [0.0] * 6

    model = DummyModel()
    gen = harmony.HarmonyGenerator(model)
    rhythm = [1.0] * 8  # two bars
    chords, _ = gen.generate("C", ["C4"], rhythm)
    assert model.calls == 2
    # Ensure returned chords correspond to degree zero
    assert all(c == "C" for c in chords)


@pytest.mark.parametrize(
    "time_signature",
    [
        (-4, 4),  # negative numerator should be rejected
        (4, 0),   # zero denominator would trigger division by zero
        (4, -4),  # negative denominator is musically invalid
        (4, 3),   # denominator outside the allowed simple set should fail
    ],
)
def test_harmony_generator_rejects_invalid_time_signature(time_signature):
    """``generate`` should validate time signature components."""
    harmony = importlib.import_module("melody_generator.harmony_generator")
    gen = harmony.HarmonyGenerator()
    rhythm = [1.0] * 4  # one bar of 4/4
    with pytest.raises(ValueError):
        gen.generate("C", ["C4"], rhythm, time_signature=time_signature)


@pytest.mark.parametrize("denominator", [1, 2, 4, 8, 16])
def test_harmony_generator_accepts_common_denominator(denominator):
    """Generator should allow simple meter denominators without error."""
    harmony = importlib.import_module("melody_generator.harmony_generator")
    gen = harmony.HarmonyGenerator()
    # Construct a rhythm that spans exactly one bar for the given meter so
    # bar counting remains consistent across denominations.
    beats_per_bar = int(4 * (4 / denominator))
    rhythm = [1.0] * beats_per_bar
    chords, durations = gen.generate(
        "C", ["C4"], rhythm, time_signature=(4, denominator)
    )
    # Only one bar of chords should be produced and duration should match beats per bar
    assert len(chords) == 1
    assert durations == [4 * (4 / denominator)]
