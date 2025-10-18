"""Tests for :func:`melody_generator.midi_to_degrees` conversion helper.

These unit tests focus on the dataset-preparation function that converts MIDI
note-on events to scale-degree indices. The scenarios cover the most critical
requirements:

* Mapping an in-memory :class:`mido.MidiFile` containing diatonic notes to the
  expected integer sequence.
* Preserving chronological ordering when notes span multiple tracks by sorting
  on absolute tick values before mapping.
* Optionally dropping chromatic tones when ``drop_out_of_key`` is enabled while
  default behaviour snaps them to the nearest diatonic degree.
* Raising a descriptive ``ValueError`` when a file contains no qualifying
  events so dataset builders receive immediate feedback.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

# ``melody_generator`` is widely imported throughout the test suite with a stubbed
# ``mido`` dependency. The new ``midi_to_degrees`` helper requires the real
# library, so this module temporarily installs the genuine package before
# reloading ``melody_generator``. The original stub (if any) is restored after the
# tests complete so other modules continue to observe their expected behaviour.
_ORIGINAL_MIDO = sys.modules.get("mido")
if "mido" in sys.modules:
    sys.modules.pop("mido")
importlib.import_module("mido")

import melody_generator as _melody_generator

melody_generator = importlib.reload(_melody_generator)
from mido import Message, MidiFile, MidiTrack


@pytest.fixture(scope="module", autouse=True)
def _restore_mido_module():
    """Reinstate whichever ``mido`` module the wider suite expects."""

    try:
        yield
    finally:
        if _ORIGINAL_MIDO is not None:
            sys.modules["mido"] = _ORIGINAL_MIDO
        else:
            sys.modules.pop("mido", None)
        if "melody_generator" in sys.modules:
            importlib.reload(sys.modules["melody_generator"])


def _write_midi(tmp_path: Path, notes: list[int]) -> Path:
    """Helper that writes a one-track MIDI file containing ``notes``.

    Each note is emitted as a ``note_on`` with an accompanying ``note_off`` so
    the resulting file mirrors the minimal structure produced by the generator.
    """

    midi = MidiFile()
    track = MidiTrack()
    midi.tracks.append(track)
    for note in notes:
        track.append(Message("note_on", note=note, velocity=64, time=0))
        track.append(Message("note_off", note=note, velocity=0, time=120))
    path = tmp_path / "sequence.mid"
    midi.save(path)
    return path


def test_midi_to_degrees_basic_sequence(tmp_path: Path) -> None:
    """Diatonic C-major notes should map directly to degrees 0..2."""

    midi_path = _write_midi(tmp_path, [60, 62, 64])  # C4, D4, E4
    result = melody_generator.midi_to_degrees(midi_path, "C")

    # The tones lie squarely in the key so their degrees increment linearly.
    assert result == [0, 1, 2]


def test_midi_to_degrees_sorts_cross_track_events() -> None:
    """Events should be ordered by absolute time even when split across tracks."""

    midi = MidiFile()

    # First track schedules an early E (64) followed by a later G (67).
    track_a = MidiTrack()
    track_a.append(Message("note_on", note=64, velocity=64, time=0))
    track_a.append(Message("note_off", note=64, velocity=0, time=240))
    track_a.append(Message("note_on", note=67, velocity=64, time=120))
    midi.tracks.append(track_a)

    # Second track introduces a middle event (F, 65) after 120 ticks. The
    # absolute-time accumulation should place it between the first two notes.
    track_b = MidiTrack()
    track_b.append(Message("note_on", note=65, velocity=64, time=120))
    midi.tracks.append(track_b)

    result = melody_generator.midi_to_degrees(midi, "C")

    # C major degrees: E -> 2, F -> 3, G -> 4. Ordering must reflect absolute
    # timing rather than track append order.
    assert result == [2, 3, 4]


def test_midi_to_degrees_drop_out_of_key(tmp_path: Path) -> None:
    """Chromatic tones are skipped when ``drop_out_of_key`` is enabled."""

    midi_path = _write_midi(tmp_path, [60, 68])  # C4 (in key) and G#4 (chromatic)

    # Default behaviour snaps the G# to the nearest scale degree (G) yielding
    # indices [0, 4]. When ``drop_out_of_key`` is ``True`` only the tonic remains.
    snapped = melody_generator.midi_to_degrees(midi_path, "C")
    filtered = melody_generator.midi_to_degrees(
        midi_path, "C", drop_out_of_key=True
    )

    assert snapped == [0, 4]
    assert filtered == [0]


def test_midi_to_degrees_raises_on_empty(tmp_path: Path) -> None:
    """Missing ``note_on`` messages should trigger a clear validation error."""

    empty_midi = MidiFile()
    empty_midi.tracks.append(MidiTrack())
    path = tmp_path / "empty.mid"
    empty_midi.save(path)

    with pytest.raises(ValueError, match="note_on events"):
        melody_generator.midi_to_degrees(path, "C")
