"""Unit tests for note ↔ MIDI conversion helpers.

These tests exercise both :func:`note_to_midi` and :func:`midi_to_note`. The
goal is to ensure round-trip conversions behave as expected, while invalid
inputs result in descriptive errors instead of silent failures."""

import sys
from pathlib import Path
import types
import importlib
import pytest

# Provide a minimal dummy 'mido' module so the script can be imported without the dependency
mido_stub = types.ModuleType('mido')
mido_stub.Message = object
mido_stub.MidiFile = object
mido_stub.MidiTrack = object
def bpm2tempo(bpm):
    return bpm
mido_stub.bpm2tempo = bpm2tempo
mido_stub.MetaMessage = object
sys.modules['mido'] = mido_stub

# Provide a minimal stub for the 'tkinter' module so the import succeeds
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
note_to_midi = melody_generator.note_to_midi
midi_to_note = melody_generator.midi_to_note
note_utils_mod = importlib.import_module("melody_generator.note_utils")


def test_sharp_conversion():
    """Sharp notes convert to their expected MIDI numbers."""
    assert note_to_midi('C#4') == 61


def test_flat_conversion():
    """Flat notes produce the same value as their enharmonic sharps."""
    assert note_to_midi('Db4') == 61


def test_multi_digit_octaves_and_range_validation():
    """Multi-digit octaves parse correctly and out-of-range values error.

    ``note_to_midi`` previously clamped values beyond the MIDI limits. The
    helper now raises ``ValueError`` so callers cannot unknowingly exceed the
    valid range. We test both a valid multi-digit octave and two out-of-range
    examples.
    """

    # Valid multi-digit octave (within 0-127).
    assert note_to_midi('C8') == 108
    assert note_to_midi('Gb9') == 126

    # Octaves that would map beyond MIDI 127 should raise an error.
    with pytest.raises(ValueError, match="out of range"):
        note_to_midi('C10')
    with pytest.raises(ValueError, match="out of range"):
        note_to_midi('Gb11')


def test_negative_octaves_raise_value_error():
    """Notes mapping below MIDI 0 raise ``ValueError`` instead of clamping."""

    # ``C-1`` represents MIDI note 0 and is valid.
    assert note_to_midi('C-1') == 0

    # Octaves below ``-1`` produce negative MIDI numbers and should fail.
    with pytest.raises(ValueError, match="out of range"):
        note_to_midi('C-2')


def test_unknown_note_raises_value_error(monkeypatch):
    """Unknown note names result in a descriptive ``ValueError``.

    The mapping dictionary normally includes all valid pitch classes. We
    temporarily remove one entry to simulate an unexpected note and verify the
    helper surfaces a clear error message.
    """

    monkeypatch.delitem(note_utils_mod.NOTE_TO_SEMITONE, "C", raising=False)
    note_utils_mod.note_to_midi.cache_clear()
    with pytest.raises(ValueError, match="Unknown note name: C"):
        note_utils_mod.note_to_midi("C4")


def test_midi_to_note_range_validation():
    """``midi_to_note`` rejects values outside the valid 0-127 range.

    The helper should successfully convert boundary values while flagging
    out-of-range integers. Negative numbers and values above 127 are common
    user mistakes; raising ``ValueError`` ensures the caller is alerted.
    """

    # Valid boundary conversions.
    assert midi_to_note(0) == "C-1"
    assert midi_to_note(127) == "G9"

    # Values below 0 or above 127 should raise errors.
    with pytest.raises(ValueError, match="out of range"):
        midi_to_note(-1)
    with pytest.raises(ValueError, match="out of range"):
        midi_to_note(128)

