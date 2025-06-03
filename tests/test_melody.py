import importlib.util
import pathlib
import sys
import types
import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "melody-generator.py"
spec = importlib.util.spec_from_file_location("melody_generator", MODULE_PATH)
melody_generator = importlib.util.module_from_spec(spec)

# Provide a minimal stub for the 'mido' module so the import succeeds
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *args, **kwargs: None
stub_mido.MidiFile = lambda *args, **kwargs: types.SimpleNamespace(tracks=[])
stub_mido.MidiTrack = lambda *args, **kwargs: []
stub_mido.MetaMessage = lambda *args, **kwargs: None
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

spec.loader.exec_module(melody_generator)
note_to_midi = melody_generator.note_to_midi
generate_melody = melody_generator.generate_melody


def test_note_to_midi_sharp_and_flat():
    assert note_to_midi('C#4') == note_to_midi('Db4')
    assert note_to_midi('F#5') == note_to_midi('Gb5')


def test_generate_melody_length_and_error():
    chords = ['C', 'G', 'Am', 'F']
    melody = generate_melody('C', 8, chords, motif_length=4)
    assert len(melody) == 8

    with pytest.raises(ValueError):
        generate_melody('C', 3, chords, motif_length=4)
