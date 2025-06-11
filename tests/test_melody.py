import sys
from pathlib import Path
import types
import importlib
import pytest

# Provide a minimal stub for the 'mido' module so the import succeeds
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *args, **kwargs: None
class DummyMidiFile:
    """Minimal MidiFile stub that records tracks and save calls."""
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.tracks = []
        DummyMidiFile.last_instance = self

    def save(self, _path):
        pass

stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = lambda *args, **kwargs: []
stub_mido.MetaMessage = lambda *args, **kwargs: None
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

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
generate_melody = melody_generator.generate_melody
generate_harmony_line = melody_generator.generate_harmony_line
generate_counterpoint_melody = melody_generator.generate_counterpoint_melody
create_midi_file = melody_generator.create_midi_file


def test_note_to_midi_sharp_and_flat():
    assert note_to_midi('C#4') == note_to_midi('Db4')
    assert note_to_midi('F#5') == note_to_midi('Gb5')


def test_generate_melody_length_and_error():
    chords = ['C', 'G', 'Am', 'F']
    melody = generate_melody('C', 8, chords, motif_length=4)
    assert len(melody) == 8

    with pytest.raises(ValueError):
        generate_melody('C', 3, chords, motif_length=4)


def test_extra_tracks_created(tmp_path):
    chords = ['C', 'G', 'Am', 'F']
    melody = generate_melody('C', 8, chords, motif_length=4)
    harmony = generate_harmony_line(melody)
    cp = generate_counterpoint_melody(melody, 'C')
    out = tmp_path / 'm.mid'
    create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        extra_tracks=[harmony, cp],
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None
    assert len(mid.tracks) == 1 + 2


def test_extra_tracks_shorter_line(tmp_path):
    chords = ['C', 'G', 'Am', 'F']
    melody = generate_melody('C', 6, chords, motif_length=4)
    harmony = generate_harmony_line(melody)[:3]
    cp = generate_counterpoint_melody(melody, 'C')[:5]
    out = tmp_path / 'short.mid'
    create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        extra_tracks=[harmony, cp],
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None
    assert len(mid.tracks) == 1 + 2
    assert len(mid.tracks[1]) == 2 * len(harmony)
    assert len(mid.tracks[2]) == 2 * len(cp)


def test_progression_chords_exist():
    for key in ["F", "Ab"]:
        prog = melody_generator.generate_random_chord_progression(key, 4)
        assert all(ch in melody_generator.CHORDS for ch in prog)


def test_diatonic_chords_major_minor():
    major = melody_generator.diatonic_chords("C")
    assert major == ["C", "Dm", "Em", "F", "G", "Am", "B"]

    minor = melody_generator.diatonic_chords("Am")
    assert minor == ["Am", "B", "C", "Dm", "Em", "F", "G"]


def test_melody_trends_up_then_down():
    chords = ["C", "G", "Am", "F"]
    mel = generate_melody("C", 12, chords, motif_length=4)
    midi_vals = [note_to_midi(n) for n in mel]
    mid = len(midi_vals) // 2
    first_half = midi_vals[:mid]
    second_half = midi_vals[mid:]

    up_trend = sum(b - a for a, b in zip(first_half, first_half[1:])) / (len(first_half) - 1)
    down_trend = sum(b - a for a, b in zip(second_half, second_half[1:])) / (len(second_half) - 1)

    assert up_trend >= 0
    assert down_trend <= 0
