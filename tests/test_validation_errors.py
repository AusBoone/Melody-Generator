"""Input validation tests for core melody generation helpers.

This module checks that high-level APIs raise informative errors when called with
invalid parameters. A lightweight ``mido`` stub avoids external dependencies so
only the validation logic is exercised.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

# Minimal 'mido' stub so the package imports without the real library.
stub_mido = types.ModuleType("mido")

class DummyMessage:
    """Simple MIDI message representation used during tests."""

    def __init__(self, _type: str, **kw) -> None:
        self.type = _type
        self.time = kw.get("time", 0)
        self.note = kw.get("note")
        self.velocity = kw.get("velocity")
        self.program = kw.get("program")


class DummyMidiFile:
    """Collects MIDI tracks written by the functions under test."""

    def __init__(self, *args, **kwargs) -> None:
        self.tracks = []

    def save(self, _path: str) -> None:  # pragma: no cover - no disk IO
        pass


class DummyMidiTrack(list):
    """Container for MIDI events in lieu of ``mido.MidiTrack``."""


stub_mido.Message = DummyMessage
stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = DummyMidiTrack
stub_mido.MetaMessage = lambda *args, **kwargs: DummyMessage("meta", **kwargs)
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

# Stub 'tkinter' for modules that reference the GUI library.
tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

# Import the package after installing stubs so initialization succeeds.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
mg = importlib.import_module("melody_generator")
create_midi_file = mg.create_midi_file
MIN_OCTAVE = mg.MIN_OCTAVE
MAX_OCTAVE = mg.MAX_OCTAVE
PolyphonicGenerator = importlib.import_module("melody_generator.polyphony").PolyphonicGenerator
validate_time_signature = importlib.import_module(
    "melody_generator.utils"
).validate_time_signature


def test_create_midi_file_empty_chord_progression(tmp_path) -> None:
    """``create_midi_file`` should reject an empty ``chord_progression`` list."""

    melody = ["C4"] * 4
    out = tmp_path / "out.mid"
    # A zero-length chord progression provides no harmonic context; the helper
    # explicitly checks for this and raises ``ValueError`` so callers can fix
    # their input before any MIDI is produced.
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 4), str(out), chord_progression=[])


@pytest.mark.parametrize("bpm", [0, -120])
def test_create_midi_file_invalid_bpm(bpm: int, tmp_path) -> None:
    """``create_midi_file`` should reject non-positive ``bpm`` values."""

    melody = ["C4"]
    out = tmp_path / "out.mid"
    # Tempo defines note spacing; zero or negative BPM is nonsensical and must
    # raise ``ValueError`` so callers correct their input before file creation.
    with pytest.raises(ValueError):
        create_midi_file(melody, bpm, (4, 4), str(out))


def test_generate_base_octaves_out_of_range() -> None:
    """``generate`` should validate octave overrides for each voice."""

    gen = PolyphonicGenerator()
    # Each invalid entry is checked independently; using an out-of-range octave
    # for any voice should cause ``ValueError``.
    with pytest.raises(ValueError):
        gen.generate("C", 4, ["C"], base_octaves={"soprano": MIN_OCTAVE - 1})
    with pytest.raises(ValueError):
        gen.generate("C", 4, ["C"], base_octaves={"alto": MAX_OCTAVE + 1})


def test_validate_time_signature_success() -> None:
    """Typical time signatures should parse into integer tuples."""

    assert validate_time_signature("4/4") == (4, 4)
    assert validate_time_signature("7/8") == (7, 8)


def test_validate_time_signature_textual_aliases() -> None:
    """Musicians often enter common/cut time by name—ensure those aliases work."""

    # Common-time aliases should round-trip to 4/4 regardless of spacing or case.
    assert validate_time_signature("C") == (4, 4)
    assert validate_time_signature("common time") == (4, 4)
    assert validate_time_signature(" CommonTime ") == (4, 4)

    # Cut-time / alla breve aliases should map to 2/2, including the Unicode ¢ symbol.
    assert validate_time_signature("C|") == (2, 2)
    assert validate_time_signature("alla breve") == (2, 2)
    assert validate_time_signature("CuT TiMe") == (2, 2)
    assert validate_time_signature("¢") == (2, 2)


@pytest.mark.parametrize(
    "value",
    ["4", "3/5", "0/4", "-2/4", "A/B"],
)
def test_validate_time_signature_errors(value: str) -> None:
    """Malformed or unsupported signatures should raise ``ValueError``."""

    with pytest.raises(ValueError):
        validate_time_signature(value)
