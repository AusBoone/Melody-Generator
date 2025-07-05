"""Unit tests for the ``note_to_midi`` helper.

The helper converts note names such as ``C#4`` or ``Db4`` into MIDI numbers.
These tests confirm that enharmonic spellings map to the same value."""

import sys
from pathlib import Path
import types
import importlib

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


def test_sharp_conversion():
    """Sharp notes convert to their expected MIDI numbers."""
    assert note_to_midi('C#4') == 61


def test_flat_conversion():
    """Flat notes produce the same value as their enharmonic sharps."""
    assert note_to_midi('Db4') == 61


def test_multi_digit_octaves():
    """Octaves with multiple digits convert correctly.

    This ensures ``note_to_midi`` handles values like ``C10`` or ``Gb11`` by
    reading all trailing digits instead of only the last character.
    """
    assert note_to_midi('C10') == 127  # values above 127 are clamped
    assert note_to_midi('Gb11') == 127


def test_negative_octaves_clamped():
    """Notes below MIDI 0 clamp to 0."""
    assert note_to_midi('C-2') == 0
