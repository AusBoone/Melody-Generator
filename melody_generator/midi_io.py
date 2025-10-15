"""Utilities for writing MIDI files and previewing them.

Modification summary
--------------------
* ``create_midi_file`` now creates the destination directory automatically so
  callers can pass a path in a new folder without preparing it.
* ``create_midi_file`` accounts for extra inserted beats when extending the
  melody so chord tracks remain aligned with the final note.
* ``create_midi_file`` increments ``total_beats`` for rest pattern entries so
  chord tracks remain aligned even when rhythms contain rests.
* ``create_midi_file`` validates ``bpm`` is positive so invalid tempos are
  caught early.
* ``create_midi_file`` applies ``humanize_events`` to all MIDI tracks so timing
  jitter affects every part of the composition rather than only the melody.
* Imports from ``mido`` are deferred inside ``create_midi_file`` so the module
  can load even when the optional dependency is missing.
* ``create_midi_file`` advertises its ``MidiFile`` return type for clearer
  static type checking and easier inspection in tests.
* Added optional ornamentation placeholders that emit short grace notes on MIDI
  channel 2 so arrangers can easily identify suggested trill or mordent
  locations when importing the file into notation software.

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
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    # ``MidiFile`` is only needed for type checking to avoid requiring the
    # optional dependency at import time.
    from mido import MidiFile

from . import (
    CHORDS,
    canonical_chord,
    generate_rhythm,
    humanize_events,
    note_to_midi,
)

__all__ = ["create_midi_file", "_open_default_player"]

# MIDI channel reserved for ornamentation placeholders. Channels are zero-based
# in the MIDI specification, so ``1`` corresponds to what performers typically
# refer to as “channel 2”. Keeping this constant centralised ensures both the
# generation logic and tests agree on the chosen channel.
ORNAMENT_CHANNEL = 1


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
    *,
    ornaments: bool = False,
) -> "MidiFile":
    """Write ``melody`` to ``output_file`` as a MIDI file.

    The generated ``MidiFile`` is returned so callers and tests can inspect the
    in-memory representation without reading the written file back from disk.
    Chord names supplied via ``chord_progression`` are canonicalised using
    :func:`canonical_chord` so case-insensitive input is accepted. Unknown
    chords raise ``ValueError`` before any MIDI events are created. The parent
    directory of ``output_file`` is created automatically so callers may supply
    paths in a new folder without preparing it beforehand. Notes starting a
    measure receive a small velocity accent to provide a subtle rhythmic pulse.

    Returns
    -------
    MidiFile
        In-memory representation of the written file for further inspection or
        reuse without reloading from disk.

    Other Parameters
    ----------------
    ornaments:
        When ``True`` an additional MIDI track is emitted on channel 2 containing
        short grace-note placeholders at the start of each sounded melody note.
        These markers give arrangers an obvious place to add trills or mordents
        after importing the file into notation software. The placeholders use a
        small velocity so they are audible but unobtrusive when previewing.
    """
    # ``mido`` is imported lazily so projects depending on this module do not
    # need the optional MIDI dependency unless they actually render files.  A
    # clear error message guides users on how to install the requirement.
    try:
        import mido
        from mido import Message, MidiFile, MidiTrack
    except ModuleNotFoundError as exc:
        raise ImportError(
            "mido is required to create MIDI files; install it with 'pip install mido'"
        ) from exc

    # ``bpm`` determines the tempo of the piece; values less than or equal to
    # zero would yield invalid timing information. Validate early so callers
    # receive a clear error instead of generating a nonsensical MIDI file.
    if bpm <= 0:
        raise ValueError("bpm must be a positive integer")

    if chord_progression is not None and not chord_progression:
        raise ValueError("chord_progression must contain at least one chord")
    # Normalize chord names so callers can pass lowercase values. Unknown names
    # trigger ``ValueError`` here before any MIDI events are generated.
    if chord_progression is not None:
        chord_progression = [canonical_chord(ch) for ch in chord_progression]
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

    ornament_track: Optional[MidiTrack] = None
    ornament_pending = 0
    if ornaments:
        # Ornament placeholders live on their own track to keep the main melody
        # clean and to ensure notation software can hide or revoice them easily.
        ornament_track = MidiTrack()
        mid.tracks.append(ornament_track)
        ornament_track.append(
            Message(
                "program_change",
                program=program,
                time=0,
                channel=ORNAMENT_CHANNEL,
            )
        )

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
    rest_ticks = 0
    last_note = None
    last_velocity = 64

    total_beats = 0.0

    for i, note in enumerate(melody):
        duration_fraction = pattern[i % len(pattern)]
        # Base dynamics are intentionally conservative so compositions retain
        # headroom.  Values between ``40`` and ``60`` give a gentle curve while
        # still leaving room for expressive accents.
        base_velocity = random.randint(40, 60)
        velocity = base_velocity
        # Emphasise the first beat of each measure with a small velocity boost.
        # ``beats_elapsed`` tracks progress within the current bar and resets
        # to ``0`` once the end is reached, so a value of ``0`` indicates a
        # downbeat.
        if beats_elapsed == 0:
            velocity = min(base_velocity + 10, 127)
        if duration_fraction == 0:
            rest_ticks += beat_ticks
            beats_elapsed += 1
            # ``total_beats`` tracks the full length of the piece for chord
            # scheduling. Rests advance musical time just like sounded notes, so
            # update the accumulator here to keep harmony alignment accurate.
            total_beats += 1
            if ornament_track is not None:
                # Advance the ornament track's timeline by the same rest so the
                # next grace note remains aligned with the upcoming melody note.
                ornament_pending += beat_ticks
            continue

        note_duration = int(duration_fraction * whole_note_ticks)
        midi_note = note_to_midi(note)

        note_on = Message("note_on", note=midi_note, velocity=velocity, time=rest_ticks)
        note_off = Message("note_off", note=midi_note, velocity=velocity, time=note_duration)
        track.append(note_on)
        track.append(note_off)
        if ornament_track is not None:
            # ``ornament_pending`` accumulates the elapsed ticks since the last
            # ornament event. Incorporate the rest preceding the note so the
            # placeholder aligns with the melody onset.
            ornament_pending += rest_ticks
            grace_duration = max(1, note_duration // 8)
            grace_pitch = min(midi_note + 1, 127)
            grace_velocity = min(velocity + 5, 90)
            ornament_track.append(
                Message(
                    "note_on",
                    note=grace_pitch,
                    velocity=grace_velocity,
                    time=ornament_pending,
                    channel=ORNAMENT_CHANNEL,
                )
            )
            ornament_track.append(
                Message(
                    "note_off",
                    note=grace_pitch,
                    velocity=grace_velocity,
                    time=grace_duration,
                    channel=ORNAMENT_CHANNEL,
                )
            )
            # After scheduling the placeholder, carry forward the remaining
            # duration so subsequent ornaments know how long to wait.
            ornament_pending = max(0, note_duration - grace_duration)
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
        if beats_elapsed >= beats_per_segment:
            if last_note is not None and random.random() < 0.5:
                extra_fraction = random.choice([0.5, 1.0])
                extra_ticks = int(extra_fraction * whole_note_ticks)
                on = Message("note_on", note=last_note, velocity=last_velocity, time=0)
                off = Message(
                    "note_off", note=last_note, velocity=last_velocity, time=extra_ticks
                )
                track.append(on)
                track.append(off)

                # The randomly inserted extra note extends the overall piece.
                # Update the beat counters so chord and measure calculations
                # include the additional duration.
                total_beats += extra_fraction
                beats_elapsed += extra_fraction

                if ornament_track is not None:
                    # Match the ornament timeline to the extended sustain so
                    # subsequent grace notes remain synchronised with the
                    # elongated melody segment.
                    ornament_pending += extra_ticks

                rest_ticks = beat_ticks
            # Reset the segment counter after any optional extension so the
            # next measure begins at beat zero.
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
        # Apply humanization to every track so harmony and auxiliary parts
        # receive the same timing variations as the melody track. Ornament
        # placeholders remain untouched so their precise alignment continues to
        # signal where performers might add embellishments.
        for midi_track in mid.tracks:
            if ornament_track is not None and midi_track is ornament_track:
                continue
            humanize_events(midi_track)

    # Ensure the destination directory exists so ``mid.save`` succeeds even
    # when the caller specifies a path in a new folder.
    Path(output_file).expanduser().parent.mkdir(parents=True, exist_ok=True)

    mid.save(output_file)
    logging.info("MIDI file saved to %s", output_file)
    # Returning the ``MidiFile`` instance allows callers and tests to inspect
    # the in-memory representation without reloading the written file.
    return mid


def _open_default_player(path: str, *, delete_after: bool = False) -> None:
    """Launch ``path`` asynchronously with the system default MIDI player.

    ``open_default_player`` blocks until the external program exits, so this
    helper spawns the call in a daemon thread to avoid freezing the caller's
    UI.  The thread removes ``path`` after playback when ``delete_after`` is
    ``True``.  Concurrent calls create separate threads, so they are thread
    safe as long as distinct file paths are used.  Reusing the same temporary
    file could result in one thread deleting it while another still needs it.
    """

    from .playback import open_default_player

    def runner() -> None:
        try:
            open_default_player(path, delete_after=delete_after)
        except Exception as exc:  # pragma: no cover - platform dependent
            logging.error("Could not open MIDI file: %s", exc)

    threading.Thread(target=runner, daemon=True).start()

