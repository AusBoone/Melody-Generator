"""Regression tests for ``PolyphonicGenerator._enforce_voice_leading``.

These tests construct extreme voice configurations to ensure octave shifts
never yield invalid MIDI values and that basic crossing/spacing rules are
applied correctly.

The ``mido`` and ``tkinter`` modules are stubbed so the import of
``melody_generator`` succeeds without optional dependencies.
"""

import types
import importlib
import sys
from pathlib import Path


# Create minimal 'mido' stub so the polyphony module can be imported without the
# real MIDI library. Only the attributes accessed during tests are provided.
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *a, **kw: None
stub_mido.MidiFile = type("MidiFile", (object,), {"__init__": lambda self, *a, **kw: None})
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: None
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

# Provide a very small ``tkinter`` stub to satisfy optional GUI imports.
tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
for name in ["tkinter", "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk"]:
    sys.modules.setdefault(name, getattr(tk_stub, name.split(".")[-1], tk_stub))

# Add project root to ``sys.path`` so local packages resolve correctly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

polyphony = importlib.import_module("melody_generator.polyphony")
mg = importlib.import_module("melody_generator")
PolyphonicGenerator = polyphony.PolyphonicGenerator
note_to_midi = mg.note_to_midi


def test_crossing_near_midi_limits():
    """Crossed voices at the top of the MIDI range should lower the lower part.

    ``soprano`` and ``alto`` start inverted near ``G9``. The soprano cannot be
    raised an octave because that would exceed ``127``. Instead, ``alto`` is
    shifted down while the remaining voices are adjusted for spacing.
    """

    gen = PolyphonicGenerator()
    voices = {
        "soprano": ["F9"],  # MIDI 125
        "alto": ["G9"],     # MIDI 127, above soprano
        "tenor": ["C4"],
        "bass": ["C3"],
    }

    gen._enforce_voice_leading(voices)

    # Alto should move down an octave because soprano cannot move up
    assert voices["alto"][0] == "G8"
    # Tenor and bass are raised to maintain spacing
    assert voices["tenor"][0] == "C5"
    assert voices["bass"][0] == "C4"

    # All resulting notes must remain valid MIDI numbers
    for v in gen.voices:
        assert 0 <= note_to_midi(voices[v][0]) <= 127


def test_wide_spacing_reduces_to_single_octave():
    """Voices spaced over an octave apart should be lifted up one octave.

    The initial lines have gaps of more than twelve semitones between each
    adjacent pair. After enforcement, every gap should be at most one octave
    while all notes stay within the MIDI range.
    """

    gen = PolyphonicGenerator()
    voices = {
        "soprano": ["C5"],  # MIDI 72
        "alto": ["E3"],    # MIDI 52
        "tenor": ["C3"],   # MIDI 48
        "bass": ["C2"],    # MIDI 36
    }

    gen._enforce_voice_leading(voices)

    # Check that each adjacent pair is no more than an octave apart
    midis = [note_to_midi(voices[v][0]) for v in gen.voices]
    for hi, lo in zip(midis, midis[1:]):
        assert hi - lo <= 12
        assert 0 <= hi <= 127
        assert 0 <= lo <= 127

    # Specific shifts expected from the test setup
    assert voices["alto"][0] == "E4"
    assert voices["tenor"][0] == "C4"
    assert voices["bass"][0] == "C3"
