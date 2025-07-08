"""Utilities for writing MIDI files and previewing them.

This module contains the low-level helpers used to render melodies as MIDI and
open the resulting files with the user's default player. It is separated from
the main package so applications can use the MIDI functionality without
importing the full CLI.
"""

from __future__ import annotations

import logging
import math
import random
import threading
from typing import List, Optional, Tuple

import mido
from mido import Message, MidiFile, MidiTrack

from . import CHORDS, generate_rhythm, humanize_events, note_to_midi

__all__ = ["create_midi_file", "_open_default_player"]


def create_midi_file(
    melody: List[str],
    bpm: int,
    time_signature: Tuple[int, int],
    output_file: str,
    harmony: bool = False,
    pattern: Optional[List[float]] = None,
    extra_tracks: Optional[List[List[str]]] = None,
    chord_progression: Optional[List[str]] = None,
    chords_separate: bool = True,
    program: int = 0,
    humanize: bool = True,
) -> None:
    """Write ``melody`` to ``output_file`` as a MIDI file."""

    if chord_progression is not None and not chord_progression:
        raise ValueError("chord_progression must contain at least one chord")
    valid_denoms = {1, 2, 4, 8, 16}
    if (time_signature[0] <= 0 or time_signature[1] <= 0 or
            time_signature[1] not in valid_denoms):
        raise ValueError(
            "time_signature denominator must be one of 1, 2, 4, 8 or 16 and numerator must be > 0"
        )
    ticks_per_beat = 480
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    harmony_track = None
    if harmony:
        harmony_track = MidiTrack()
        mid.tracks.append(harmony_track)
    extra_midi_tracks: List[MidiTrack] = []
    if extra_tracks:
        for _ in extra_tracks:
            t = MidiTrack()
            mid.tracks.append(t)
            extra_midi_tracks.append(t)

    chord_track: Optional[MidiTrack] = None
    if chord_progression:
        chord_track = track if not chords_separate else MidiTrack()
        if chords_separate:
            mid.tracks.append(chord_track)

    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
    track.append(
        mido.MetaMessage(
            "time_signature", numerator=time_signature[0], denominator=time_signature[1]
        )
    )
    track.append(Message("program_change", program=program, time=0))

    if pattern is None:
        pattern = generate_rhythm(len(melody))
    elif not pattern:
        raise ValueError("pattern must not be empty")
    elif any(p < 0 for p in pattern):
        raise ValueError("pattern durations must be non-negative")
    whole_note_ticks = ticks_per_beat * 4
    beat_fraction = 1 / time_signature[1]
    beat_ticks = int(beat_fraction * whole_note_ticks)
    beats_per_segment = time_signature[0]
    beats_elapsed = 0
    start_beat = 0.0
    rest_ticks = 0
    last_note = None
    last_velocity = 64

    total_beats = 0.0

    for i, note in enumerate(melody):
        duration_fraction = pattern[i % len(pattern)]
        velocity = random.randint(50, 90)
        if duration_fraction == 0:
            rest_ticks += beat_ticks
            beats_elapsed += 1
            start_beat += 1
            continue

        note_duration = int(duration_fraction * whole_note_ticks)
        midi_note = note_to_midi(note)

        note_on = Message("note_on", note=midi_note, velocity=velocity, time=rest_ticks)
        note_off = Message("note_off", note=midi_note, velocity=velocity, time=note_duration)
        track.append(note_on)
        track.append(note_off)
        if harmony_track is not None:
            harmony_note = min(midi_note + 4, 127)
            h_on = Message(
                "note_on",
                note=harmony_note,
                velocity=max(velocity - 10, 40),
                time=rest_ticks,
            )
            h_off = Message(
                "note_off",
                note=harmony_note,
                velocity=max(velocity - 10, 40),
                time=note_duration,
            )
            harmony_track.append(h_on)
            harmony_track.append(h_off)
        for line, t in zip(extra_tracks or [], extra_midi_tracks):
            if i >= len(line):
                continue
            m = note_to_midi(line[i])
            x_on = Message("note_on", note=m, velocity=velocity, time=rest_ticks)
            x_off = Message("note_off", note=m, velocity=velocity, time=note_duration)
            t.append(x_on)
            t.append(x_off)

        rest_ticks = 0
        beat_len = duration_fraction / beat_fraction
        beats_elapsed += beat_len
        total_beats += beat_len
        last_note = midi_note
        last_velocity = velocity
        start_beat += beat_len

        if beats_elapsed >= beats_per_segment:
            if last_note is not None and random.random() < 0.5:
                extra_fraction = random.choice([0.5, 1.0])
                extra_ticks = int(extra_fraction * whole_note_ticks)
                on = Message("note_on", note=last_note, velocity=last_velocity, time=0)
                off = Message("note_off", note=last_note, velocity=last_velocity, time=extra_ticks)
                track.append(on)
                track.append(off)
                rest_ticks = beat_ticks
            beats_elapsed = 0

    if chord_track is not None:
        ticks_per_measure = int(time_signature[0] * ticks_per_beat * (4 / time_signature[1]))
        ticks_per_chord = ticks_per_measure
        total_ticks = int(total_beats * ticks_per_beat * (4 / time_signature[1]))
        num_chords = max(1, math.ceil(total_ticks / ticks_per_chord))

        chord_events: List[Tuple[int, Message]] = []
        for i in range(num_chords):
            start_tick = i * ticks_per_chord
            chord = chord_progression[i % len(chord_progression)]
            notes = CHORDS.get(chord, [])
            for note in notes:
                note_num = note_to_midi(note + "3")
                chord_events.append((start_tick, Message("note_on", note=note_num, velocity=60, time=0)))
                chord_events.append((start_tick + ticks_per_chord, Message("note_off", note=note_num, velocity=60, time=0)))

        if chords_separate:
            chord_events.sort(key=lambda p: p[0])
            last = 0
            for tick, msg in chord_events:
                msg.time = tick - last
                chord_track.append(msg)
                last = tick
        else:
            merged_events: List[Tuple[int, Message]] = []
            current = 0
            for msg in track:
                current += msg.time
                merged_events.append((current, msg))
            merged_events.extend(chord_events)
            merged_events.sort(key=lambda p: p[0])

            track.clear()
            last = 0
            for tick, msg in merged_events:
                msg.time = tick - last
                track.append(msg)
                last = tick

    if humanize:
        humanize_events(mid.tracks[0])

    mid.save(output_file)
    logging.info("MIDI file saved to %s", output_file)


def _open_default_player(path: str, *, delete_after: bool = False) -> None:
    """Launch ``path`` asynchronously with the system default MIDI player."""

    from .playback import open_default_player

    def runner() -> None:
        try:
            open_default_player(path, delete_after=delete_after)
        except Exception as exc:  # pragma: no cover - platform dependent
            logging.error("Could not open MIDI file: %s", exc)

    threading.Thread(target=runner, daemon=True).start()

