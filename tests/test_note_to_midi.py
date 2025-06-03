import importlib.util
import sys
import types
from pathlib import Path

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

spec = importlib.util.spec_from_file_location(
    'melody_generator',
    Path(__file__).resolve().parents[1] / 'melody-generator.py',
)
melody_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(melody_generator)

note_to_midi = melody_generator.note_to_midi


def test_sharp_conversion():
    assert note_to_midi('C#4') == 61


def test_flat_conversion():
    assert note_to_midi('Db4') == 61
