import sys
from pathlib import Path
import types
import importlib
import pytest
import random

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


def test_generate_melody_invalid_denominator():
    chords = ['C', 'G']
    with pytest.raises(ValueError):
        generate_melody('C', 4, chords, motif_length=4, time_signature=(4, 0))


def test_generate_melody_invalid_numerator_and_negative_denominator():
    chords = ['C', 'G']
    with pytest.raises(ValueError):
        generate_melody('C', 4, chords, motif_length=4, time_signature=(0, 4))
    with pytest.raises(ValueError):
        generate_melody('C', 4, chords, motif_length=4, time_signature=(4, -1))


def test_create_midi_file_invalid_time_signature(tmp_path):
    melody = ['C4'] * 4
    out = tmp_path / 'bad.mid'
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (0, 4), str(out))
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 0), str(out))
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, -3), str(out))


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


def test_chord_track_added(tmp_path):
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "ch.mid"
    create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        chord_progression=chords,
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None
    assert len(mid.tracks) == 2


def test_chords_on_same_track(tmp_path):
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "merge.mid"
    create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        chord_progression=chords,
        chords_separate=False,
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None
    assert len(mid.tracks) == 1


def test_rest_values_in_pattern(tmp_path):
    chords = ["C", "G", "Am", "F"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "rest.mid"
    create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25, 0],
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None
    # Two meta messages plus one pair of events for each non-rest note
    assert len(mid.tracks[0]) == 6


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
    random.seed(0)
    mel = generate_melody("C", 12, chords, motif_length=4)
    midi_vals = [note_to_midi(n) for n in mel]
    mid = len(midi_vals) // 2
    first_half = midi_vals[:mid]
    second_half = midi_vals[mid:]

    up_trend = sum(b - a for a, b in zip(first_half, first_half[1:])) / (len(first_half) - 1)
    down_trend = sum(b - a for a, b in zip(second_half, second_half[1:])) / (len(second_half) - 1)

    assert up_trend >= 0
    assert down_trend <= 0


def test_downbeats_match_chords():
    chords = ["C", "G", "Am", "F"]
    pattern = [0.25]
    mel = generate_melody(
        "C",
        8,
        chords,
        motif_length=4,
        time_signature=(4, 4),
        pattern=pattern,
    )
    beat_unit = 1 / 4
    start = 0.0
    for i, note in enumerate(mel):
        if abs(start - round(start)) < 1e-6:
            chord = chords[i % len(chords)]
            assert note[:-1] in melody_generator.CHORDS[chord]
        start += pattern[i % len(pattern)] / beat_unit


def test_base_octave_range(monkeypatch):
    chords = ["C", "G", "Am", "F"]
    monkeypatch.setattr(melody_generator.random, "random", lambda: 0.5)
    mel = generate_melody("C", 8, chords, motif_length=4, base_octave=3)
    assert {int(n[-1]) for n in mel}.issubset({3, 4})


def test_octave_shift_occurs(monkeypatch):
    chords = ["C", "G", "Am", "F"]
    seq = iter([0.05])

    monkeypatch.setattr(
        melody_generator.random,
        "random",
        lambda: next(seq, 0.5),
    )

    orig_choice = melody_generator.random.choice

    def choice(seq_val):
        if seq_val == [-1, 1]:
            return 1
        return orig_choice(seq_val)

    monkeypatch.setattr(melody_generator.random, "choice", choice)

    mel = generate_melody(
        "C",
        8,
        chords,
        motif_length=4,
        base_octave=4,
        pattern=[0.25],
    )
    octs = [int(n[-1]) for n in mel]
    assert any(o > 5 for o in octs)
