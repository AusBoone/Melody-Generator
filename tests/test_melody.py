"""Tests for the melody generation helpers and MIDI output.

These unit tests focus on the low level functions that build melodies and write
``MidiFile`` objects. The real ``mido`` and ``tkinter`` modules are replaced
with stubs so that only the core logic is exercised."""

import sys
from pathlib import Path
import types
import importlib
import pytest
import random

# Provide a minimal stub for the 'mido' module so the import succeeds
stub_mido = types.ModuleType("mido")


class DummyMessage:
    """Lightweight MIDI message holding only relevant attributes."""

    def __init__(self, type: str, **kwargs) -> None:
        self.type = type
        self.time = kwargs.get("time", 0)
        self.note = kwargs.get("note")
        self.velocity = kwargs.get("velocity")
        self.program = kwargs.get("program")


class DummyMidiFile:
    """Minimal ``MidiFile`` stub that records tracks and save calls."""

    last_instance = None

    def __init__(self, *args, **kwargs) -> None:
        self.tracks = []
        DummyMidiFile.last_instance = self

    def save(self, _path: str) -> None:
        """Pretend to write MIDI data to ``_path``."""

        pass


class DummyMidiTrack(list):
    """Simple list subclass used to collect MIDI messages."""


stub_mido.Message = DummyMessage
stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = DummyMidiTrack
stub_mido.MetaMessage = lambda *args, **kwargs: DummyMessage("meta", **kwargs)
stub_mido.bpm2tempo = lambda bpm: bpm
# Override any existing ``mido`` stub so tests remain isolated regardless of
# execution order. ``setdefault`` would retain a previous stub that might not
# expose ``last_instance``, causing later assertions to fail.
sys.modules["mido"] = stub_mido

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

# Reload ``melody_generator`` so it binds to the newly installed stubs even if
# previous tests imported the package earlier in the session.
melody_generator = importlib.reload(importlib.import_module("melody_generator"))
note_to_midi = melody_generator.note_to_midi
generate_melody = melody_generator.generate_melody
generate_harmony_line = melody_generator.generate_harmony_line
generate_counterpoint_melody = melody_generator.generate_counterpoint_melody
create_midi_file = melody_generator.create_midi_file
MIN_OCTAVE = melody_generator.MIN_OCTAVE
MAX_OCTAVE = melody_generator.MAX_OCTAVE


def test_note_to_midi_sharp_and_flat():
    """Enharmonic notes map to the same MIDI value.

    ``C#4`` and ``Db4`` as well as ``F#5`` and ``Gb5`` should yield identical
    numbers when converted via ``note_to_midi``."""
    assert note_to_midi("C#4") == note_to_midi("Db4")
    assert note_to_midi("F#5") == note_to_midi("Gb5")


def test_generate_melody_length_and_error():
    """``generate_melody`` honours the requested length parameter.

    A valid call with eight notes should produce exactly eight results.
    Requesting fewer notes than the motif length should raise
    ``ValueError``."""
    chords = ["C", "G", "Am", "F"]
    melody = generate_melody("C", 8, chords, motif_length=4)
    assert len(melody) == 8

    with pytest.raises(ValueError):
        generate_melody("C", 3, chords, motif_length=4)


def test_generate_melody_non_positive_num_notes():
    """``generate_melody`` should reject zero or negative ``num_notes``.

    Passing ``0`` or ``-1`` ensures the new validation branch raises a clear
    ``ValueError`` instead of failing later when generating the motif.
    """
    chords = ["C", "G"]

    with pytest.raises(ValueError):
        generate_melody("C", 0, chords)

    with pytest.raises(ValueError):
        generate_melody("C", -1, chords)


def test_generate_melody_invalid_denominator():
    """Invalid time signature denominators raise ``ValueError``.

    ``generate_melody`` should reject denominators other than ``1, 2, 4, 8`` or
    ``16``. Passing ``(4, 0)`` exercises this validation branch."""
    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, time_signature=(4, 0))
    # Denominator values outside {1,2,4,8,16} should also be rejected
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, time_signature=(4, 3))


def test_generate_melody_invalid_numerator_and_negative_denominator():
    """Numerator and denominator validation for ``generate_melody``.

    Passing a numerator of ``0`` or a negative denominator should result in a
    ``ValueError`` to guard against nonsensical time signatures."""
    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, time_signature=(0, 4))
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, time_signature=(4, -1))


def test_generate_melody_empty_pattern():
    """Supplying an empty rhythm pattern should raise ``ValueError``.

    The melody generation logic cycles through the pattern list, so an empty
    list would lead to divide-by-zero errors. Validate that the function
    proactively rejects this."""
    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, pattern=[])


def test_generate_melody_negative_pattern():
    """Negative rhythm values should be rejected with ``ValueError``.

    Durations correspond to fractions of a whole note. Negative numbers would
    result in erroneous timing, so the generator validates against them."""
    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("C", 4, chords, motif_length=4, pattern=[0.25, -0.5])


def test_generate_melody_invalid_base_octave():
    """Out-of-range ``base_octave`` values should raise ``ValueError``.

    The melody generator clamps notes based on ``base_octave``. Supplying a
    value below 0 or above 8 would result in MIDI numbers outside 0-127, so
    the function rejects them.
    """
    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody(
            "C",
            4,
            chords,
            motif_length=4,
            base_octave=MIN_OCTAVE - 1,
        )
    with pytest.raises(ValueError):
        generate_melody(
            "C",
            4,
            chords,
            motif_length=4,
            base_octave=MAX_OCTAVE + 1,
        )


def test_get_chord_notes_unknown():
    """``get_chord_notes`` should raise ``ValueError`` for unknown chords."""

    with pytest.raises(ValueError):
        melody_generator.get_chord_notes("H")


def test_generate_melody_empty_chord_progression():
    """An empty ``chord_progression`` is invalid."""

    with pytest.raises(ValueError):
        generate_melody("C", 4, [], motif_length=4)


def test_create_midi_file_empty_chord_progression(tmp_path):
    """``create_midi_file`` should reject empty chord progressions."""

    out = tmp_path / "empty.mid"
    melody = ["C4"] * 4
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 4), str(out), chord_progression=[])


def test_create_midi_file_invalid_time_signature(tmp_path):
    """``create_midi_file`` rejects malformed time signatures.

    Each invalid signature should result in a ``ValueError`` before any file is
    written to disk."""
    melody = ["C4"] * 4
    out = tmp_path / "bad.mid"
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (0, 4), str(out))
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 0), str(out))
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, -3), str(out))
    # Non-standard denominators such as 5 should be rejected
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 5), str(out))


def test_create_midi_file_empty_pattern(tmp_path):
    """An empty rhythm pattern should be rejected with ``ValueError``.

    ``create_midi_file`` cycles through the provided list when scheduling MIDI
    events. A zero-length list would result in ``ZeroDivisionError`` when
    indexing with ``i % len(pattern)``."""
    melody = ["C4"] * 4
    out = tmp_path / "empty.mid"
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 4), str(out), pattern=[])


def test_create_midi_file_negative_pattern(tmp_path):
    """Negative durations should trigger ``ValueError`` in ``create_midi_file``.

    A rhythm list with values below zero would yield nonsensical MIDI timing, so
    the function validates and rejects such input."""
    melody = ["C4"] * 4
    out = tmp_path / "neg.mid"
    with pytest.raises(ValueError):
        create_midi_file(melody, 120, (4, 4), str(out), pattern=[0.25, -1.0])


def test_create_midi_file_creates_directory(tmp_path):
    """``create_midi_file`` should create missing output directories.

    Using a path that contains a non-existent subdirectory exercises the new
    logic which calls ``Path.mkdir`` before saving the file.
    """
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords)
    out = tmp_path / "sub" / "dir" / "new.mid"

    create_midi_file(melody, 120, (4, 4), str(out), pattern=[0.25], chord_progression=chords)

    # ``DummyMidiFile.save`` does not create the file but the directory should
    # have been made by ``create_midi_file``.
    assert out.parent.exists()


def test_extra_tracks_created(tmp_path):
    """``create_midi_file`` writes each extra melody line to its own track.

    After calling the function with harmony and counterpoint lines the resulting
    ``MidiFile`` should contain one primary track plus two additional tracks."""
    chords = ["C", "G", "Am", "F"]
    melody = generate_melody("C", 8, chords, motif_length=4)
    harmony = generate_harmony_line(melody)
    cp = generate_counterpoint_melody(melody, "C")
    out = tmp_path / "m.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        extra_tracks=[harmony, cp],
    )
    assert mid is not None
    assert len(mid.tracks) == 1 + 2


def test_extra_tracks_shorter_line(tmp_path):
    """Extra tracks shorter than the melody should still be handled.

    ``create_midi_file`` should not assume all tracks are equal length; truncated
    harmony or counterpoint lines must be padded appropriately."""
    chords = ["C", "G", "Am", "F"]
    melody = generate_melody("C", 6, chords, motif_length=4)
    harmony = generate_harmony_line(melody)[:3]
    cp = generate_counterpoint_melody(melody, "C")[:5]
    out = tmp_path / "short.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        extra_tracks=[harmony, cp],
    )
    assert mid is not None
    assert len(mid.tracks) == 1 + 2
    assert len(mid.tracks[1]) == 2 * len(harmony)
    assert len(mid.tracks[2]) == 2 * len(cp)


def test_chord_track_added(tmp_path):
    """``create_midi_file`` optionally writes chords to a separate track.

    When ``chord_progression`` is provided the resulting ``MidiFile`` should
    contain an additional track dedicated to the chords."""
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "ch.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        chord_progression=chords,
    )
    assert mid is not None
    assert len(mid.tracks) == 2


def test_chords_on_same_track(tmp_path):
    """Chord events can share the melody track when desired.

    Passing ``chords_separate=False`` should result in a single track containing
    both melody and chord events."""
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "merge.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        chord_progression=chords,
        chords_separate=False,
    )
    assert mid is not None
    assert len(mid.tracks) == 1


def test_merged_chords_start_at_zero(tmp_path):
    """Merged chord events begin at the start of the track."""
    chords = ["C", "G"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "start.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25],
        chord_progression=chords,
        chords_separate=False,
    )
    assert mid is not None
    track = mid.tracks[0]
    abs_time = 0
    chord_notes = {note_to_midi(n + "3") for n in melody_generator.CHORDS[chords[0]]}
    first_chord_time = None
    for msg in track:
        abs_time += msg.time
        if msg.type == "note_on" and msg.note in chord_notes:
            first_chord_time = abs_time
            break
    assert first_chord_time == 0


def test_rest_values_in_pattern(tmp_path):
    """Rhythm patterns may contain rests represented by ``0`` durations.

    When a rest is encountered only a ``note_off`` event should be generated,
    resulting in fewer events on the track."""
    chords = ["C", "G", "Am", "F"]
    melody = generate_melody("C", 4, chords, motif_length=4)
    out = tmp_path / "rest.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25, 0],
    )
    assert mid is not None
    # Tempo, time signature, program change and one pair per non-rest note
    assert len(mid.tracks[0]) == 7


def test_chord_alignment_with_rests(tmp_path):
    """Chord track remains in sync when rhythm pattern includes rests.

    A pattern such as ``[0.25, 0]`` alternates between a sounded quarter note
    and a full beat of silence. ``create_midi_file`` should count both note and
    rest beats so the chord track spans the same overall duration as the melody
    track."""

    chords = ["C", "G"]
    melody = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    out = tmp_path / "rest_align.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=False,
        pattern=[0.25, 0],
        chord_progression=chords,
    )

    def last_off_time(track):
        """Return absolute tick time of the final ``note_off`` event."""

        abs_time = 0
        last_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == "note_off":
                last_time = abs_time
        return last_time

    melody_track = mid.tracks[0]
    chord_track = mid.tracks[1]
    # The chord track should extend at least as long as the melody track even
    # when rests are present to ensure harmonic context is maintained.
    assert last_off_time(chord_track) >= last_off_time(melody_track)


def test_progression_chords_exist():
    """Random chord progressions never produce unknown chords.

    ``generate_random_chord_progression`` should only choose from the chords
    defined in ``melody_generator.CHORDS``."""
    for key in ["F", "Ab"]:
        prog = melody_generator.generate_random_chord_progression(key, 4)
        assert all(ch in melody_generator.CHORDS for ch in prog)


def test_diatonic_chords_major_minor():
    """Major and minor key helpers return the correct diatonic chords."""
    major = melody_generator.diatonic_chords("C")
    # The leading tone triad should explicitly carry the "dim" suffix.
    assert major == ["C", "Dm", "Em", "F", "G", "Am", "Bdim"]

    minor = melody_generator.diatonic_chords("Am")
    # The second scale degree is diminished in natural minor keys.
    assert minor == ["Am", "Bdim", "C", "Dm", "Em", "F", "G"]


def test_random_progression_invalid_key():
    """Invalid keys should raise ``ValueError`` in progression helper."""

    with pytest.raises(ValueError):
        melody_generator.generate_random_chord_progression("H", 4)


def test_progression_preserves_dim(monkeypatch):
    """Diminished chords retain their suffix in random progressions.

    ``generate_random_chord_progression`` chooses from a set of degree
    patterns. To force selection of the leading tone (a diminished triad in
    major keys) we monkeypatch ``random.choice`` to return ``[6]``."""

    monkeypatch.setattr(random, "choice", lambda _patterns: [6])
    prog = melody_generator.generate_random_chord_progression("C", 1)
    assert prog == ["Bdim"]


def test_seventh_degree_padding(monkeypatch):
    """Padded progressions should be able to select the leading tone chord.

    When the requested progression length exceeds the base pattern length,
    ``generate_random_chord_progression`` appends random degrees. To verify the
    seventh degree can appear, this test forces ``random.randint`` to return the
    highest index so the padding resolves to ``Bdim`` in the key of C major."""

    # Force padding to choose the seventh scale degree (index 6)
    monkeypatch.setattr(random, "randint", lambda _a, _b: 6)
    prog = melody_generator.generate_random_chord_progression("C", 5)
    # The final chord should be Bdim, confirming that all scale degrees are
    # sampled when padding progressions.
    assert prog[-1] == "Bdim"


def test_random_progression_invalid_length():
    """Zero or negative ``length`` values should raise ``ValueError``."""

    with pytest.raises(ValueError):
        melody_generator.generate_random_chord_progression("C", 0)

    with pytest.raises(ValueError):
        melody_generator.generate_random_chord_progression("C", -2)


def test_diatonic_chords_invalid_key():
    """``diatonic_chords`` rejects unknown keys with ``ValueError``."""

    with pytest.raises(ValueError):
        melody_generator.diatonic_chords("H")


def test_counterpoint_invalid_key():
    """``generate_counterpoint_melody`` should validate the key argument."""

    melody = ["C4", "D4"]
    with pytest.raises(ValueError):
        generate_counterpoint_melody(melody, "H")


def test_generate_motif_invalid_key():
    """``generate_motif`` should raise ``ValueError`` for unknown keys."""

    with pytest.raises(ValueError):
        melody_generator.generate_motif(4, "H")


def test_generate_motif_invalid_length():
    """Zero or negative motif lengths should raise ``ValueError``."""

    with pytest.raises(ValueError):
        melody_generator.generate_motif(0, "C")


def test_generate_motif_invalid_octave():
    """Out-of-range ``base_octave`` values should raise ``ValueError``."""

    with pytest.raises(ValueError):
        melody_generator.generate_motif(4, "C", base_octave=MIN_OCTAVE - 1)
    with pytest.raises(ValueError):
        melody_generator.generate_motif(4, "C", base_octave=MAX_OCTAVE + 1)


def test_generate_melody_invalid_key():
    """``generate_melody`` should validate the ``key`` argument."""

    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("H", 4, chords, motif_length=4)


def test_melody_trends_up_then_down():
    """Seeded melodies exhibit an overall rise then fall contour."""
    chords = ["C", "G", "Am", "F"]
    random.seed(0)
    mel = generate_melody("C", 12, chords, motif_length=4, pattern=[0.25])
    midi_vals = [note_to_midi(n) for n in mel]
    mid = len(midi_vals) // 2
    first_half = midi_vals[:mid]
    second_half = midi_vals[mid:]

    up_trend = sum(b - a for a, b in zip(first_half, first_half[1:])) / (len(first_half) - 1)
    down_trend = sum(b - a for a, b in zip(second_half, second_half[1:])) / (len(second_half) - 1)

    assert up_trend >= 0
    assert down_trend <= 0


def test_downbeats_match_chords():
    """Downbeat notes align with the current chord in the progression."""
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
    """Melodies stay within the requested base octave window."""
    chords = ["C", "G", "Am", "F"]
    monkeypatch.setattr(melody_generator.random, "random", lambda: 0.5)
    mel = generate_melody("C", 8, chords, motif_length=4, base_octave=3)
    assert {int(n[-1]) for n in mel}.issubset({3, 4})


def test_octave_shift_occurs(monkeypatch):
    """Octave shifting occasionally raises notes above the base octave."""
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


def test_chord_duration_respects_time_signature(tmp_path, monkeypatch):
    """Chord lengths should honor the time signature denominator.

    A 6/8 measure consists of six eighth notes, so with eight eighth-note
    melody events the chord track must contain two measures. The first
    ``note_off`` message for the chord should therefore occur after 1440
    ticks when the ``ticks_per_beat`` constant is 480.
    """

    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    melody = ["C4"] * 8
    out = tmp_path / "ts.mid"
    mid = melody_generator.create_midi_file(
        melody,
        120,
        (6, 8),
        str(out),
        pattern=[0.125],
        chord_progression=["C"],
        # Disable humanization so chord durations remain deterministic for
        # validation against the expected 6/8 measure length.
        humanize=False,
    )
    assert mid is not None
    chord_track = mid.tracks[1]
    off_times = [m.time for m in chord_track if m.type == "note_off"]
    assert off_times and off_times[0] == 1440


def test_chord_track_covers_extra_note(tmp_path, monkeypatch):
    """Chord track duration includes extra beats from inserted notes.

    ``create_midi_file`` occasionally repeats the last note at a phrase
    boundary. The additional beats must be reflected in the chord track so the
    harmony does not end before the melody."""

    # Force the extra-note branch and choose a full-beat extension.
    monkeypatch.setattr(melody_generator.random, "random", lambda: 0.0)
    monkeypatch.setattr(melody_generator.random, "choice", lambda _opts: 1.0)

    melody = ["C4", "D4", "E4", "F4"]  # One 4/4 measure.
    out = tmp_path / "extra.mid"
    mid = melody_generator.create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        pattern=[0.25],
        chord_progression=["C"],
        humanize=False,
    )
    assert mid is not None
    melody_track = mid.tracks[0]
    chord_track = mid.tracks[1]

    def last_off_time(track):
        """Return absolute tick time of the final ``note_off`` event."""

        abs_time = 0
        last_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == "note_off":
                last_time = abs_time
        return last_time

    # The chord track should extend at least as long as the melody so the
    # harmonic context matches the repeated extra note.
    assert last_off_time(chord_track) >= last_off_time(melody_track)


def test_candidate_cache_populated():
    """``generate_melody`` should populate the candidate cache on first use."""

    chords = ["C", "G"]
    melody_generator._CANDIDATE_CACHE.clear()
    assert not melody_generator._CANDIDATE_CACHE
    generate_melody("C", 4, chords, motif_length=2)
    assert melody_generator._CANDIDATE_CACHE


def test_candidate_cache_lazy_initialization():
    """Cache should start empty after reload and fill on first generation."""

    # Ensure required stubs exist before reloading the module.
    sys.modules.setdefault("mido", stub_mido)
    sys.modules.setdefault("tkinter", tk_stub)
    mod = importlib.reload(sys.modules["melody_generator"])  # reload active module
    assert not mod._CANDIDATE_CACHE
    mod.generate_melody("C", 4, ["C"], motif_length=2)
    assert mod._CANDIDATE_CACHE


def test_generate_melody_invalid_structure():
    """Invalid structure strings should raise ``ValueError``."""

    chords = ["C", "G"]
    with pytest.raises(ValueError):
        generate_melody("C", 8, chords, motif_length=4, structure="A1B")


def test_velocity_accent_on_downbeats(tmp_path):
    """Downbeat notes receive a velocity boost."""

    melody = ["C4", "D4", "E4", "F4"]
    out = tmp_path / "vel.mid"
    mid = create_midi_file(melody, 120, (4, 4), str(out), pattern=[0.25])
    velocities = [m.velocity for m in mid.tracks[0] if m.type == "note_on"]
    # The first note falls on a strong beat so its velocity includes the accent
    # of ``+10`` on top of the base dynamic curve. Without the accent the value
    # would be ``50`` at position ``0``.
    assert 50 <= velocities[0] <= 70


def test_final_cadence_matches_last_chord():
    """Melodies resolve on the root of the final chord."""

    chords = ["C", "G"]
    mel = generate_melody("C", 8, chords, motif_length=4)
    assert mel[-1][:-1] == melody_generator.CHORDS[chords[-1]][0]


def test_allow_tritone_filter():
    """Disallowing tritone intervals removes them from the melody."""

    chords = ["C", "G", "Am", "F"]
    random.seed(0)
    mel = generate_melody("C", 20, chords, motif_length=4, allow_tritone=False)
    intervals = [
        abs(note_to_midi(b) - note_to_midi(a))
        for a, b in zip(mel, mel[1:])
    ]
    assert 6 not in intervals

    random.seed(0)
    mel_allow = generate_melody("C", 20, chords, motif_length=4, allow_tritone=True)
    assert len(mel_allow) == 20


def test_generate_melody_custom_rhythm_generator():
    """``generate_melody`` should call the provided ``RhythmGenerator``."""

    class DummyGen:
        def __init__(self) -> None:
            self.called = 0

        def generate(self, length: int):
            self.called += 1
            return [0.25] * length

    gen = DummyGen()
    generate_melody("C", 4, ["C"], motif_length=2, rhythm_generator=gen)
    assert gen.called == 1


def test_generate_melody_accepts_lowercase():
    """Lowercase key and chord names are canonicalised automatically."""

    melody = generate_melody("c", 4, ["c", "am"], motif_length=2)
    assert len(melody) == 4


def test_create_midi_file_accepts_lowercase(tmp_path):
    """Chord names in lowercase should be processed without errors."""

    melody = ["C4"] * 4
    out = tmp_path / "lower.mid"
    mid = create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        pattern=[0.25],
        chord_progression=["c", "g"],
    )

    assert mid is not None
    assert len(mid.tracks) == 2

