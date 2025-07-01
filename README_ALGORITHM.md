# Melody Generation Algorithm

This document is aimed at readers interested in the musical and probabilistic
foundations of the generator.

## Overview

The generator constructs a concise motif and reiterates it over the requested
number of measures. Each pass through the motif may transpose or mutate the
original material, mirroring the variation techniques found in classical forms.
Candidate notes are selected from the active chord and surrounding scale tones,
yielding a small set that can be treated as a first-order Markov state. The
resulting sequence balances repetition with stochastic choice. Harmony is
specified either directly by the user or by the helper function
`generate_random_chord_progression`.

## Step-by-Step Process

1. **Motif Creation** – `generate_motif` selects random notes from the chosen key
   and places them in the provided octave range. These notes become the seed for
   the full melody.
2. **Rhythm Selection** – When no custom rhythm is provided a pattern is chosen
   from `PATTERNS`. Each element describes a note length as a fraction of a
   whole note. The pattern repeats as the melody is generated.
3. **Motif Repetition** – `generate_melody` walks through the motif and appends
   new notes until the desired length is reached. Every new phrase may shift up
   or down by a scale degree, and occasional octave jumps keep the line from
   sounding static.
4. **Chord Alignment** – On strong beats the candidate notes are restricted to
   chord tones derived from the progression so the melody naturally emphasizes
   the harmony.
5. **Interval Bias** – Small intervals are preferred when choosing the next note
   relative to the previous one. Large leaps are monitored and the next note is
   nudged in the opposite direction to smooth the contour.
6. **Fallback Logic** – If no suitable note fits the current constraints a
   random scale tone is chosen to avoid stalls. This ensures every call returns a
   complete melody.
7. **Optional Parts** – Additional helper functions create harmony lines,
   counterpoint melodies and chord tracks. These follow the same scale and chord
   rules so they blend with the main melody.

### Pseudocode Overview

```
motif = generate_motif(length, key)
pattern = choose_rhythm()
for each note_index in range(total_notes):
    chord = chord_progression[note_index % len(chord_progression)]
    allowed = restrict_to_chord(key, chord)
    next_note = pick_note(allowed, previous_note, leap_info)
    melody.append(next_note)
    update(leap_info)
```

## Design Goals

- **Simplicity** – The algorithm avoids advanced music theory so it remains
  approachable. It relies on basic principles like chord tones, scale degrees and
  rhythmic motifs.
- **Controlled Randomness** – Random choices are weighted toward musically
  pleasing outcomes. This prevents completely erratic lines while still producing
  varied results.
- **Extensibility** – Each stage can be replaced or extended, allowing future
  versions to experiment with more complex rules without rewriting the entire
  system.

For a practical example, see `generate_melody` in `melody_generator/__init__.py`
which orchestrates these steps.

## Technical Notes

This implementation is intentionally lightweight and aims for predictable
performance. The core melody construction is an **O(n)** process where *n* is
the number of notes requested. Each iteration performs a constant amount of
work—filtering a handful of candidate pitches and choosing the next note.

**Strong Beat Detection**
``generate_melody`` uses the current beat count to decide when to restrict note
choices strictly to chord tones. Beats are computed by incrementing
``start_beat`` with ``pattern[i % len(pattern)] / beat_unit``. When the current
beat aligns with an integer value within a small epsilon the note is considered
a downbeat and must match the active chord.

**Leap Tracking**
Intervals of seven semitones or larger are treated as leaps. The variable
``leap_dir`` stores their direction so the following note can bias motion back
toward the center of the melody. This keeps the overall contour smooth even when
large jumps occur.

**Overall Contour**
The phrase is intentionally asymmetrical. The first half trends upward by
incrementing scale degrees whenever a motif repeats while the second half trends
downward. The ``half_point`` index marks where this switch occurs. Octave shifts
are allowed at phrase boundaries but remain limited to one octave from the base
to maintain a focused register.

These heuristics strike a balance between structured repetition and random
variation, yielding phrases that are musically coherent without relying on
complex theory.
From a data science perspective the rules serve as priors that encode stylistic
assumptions without the need for a large training corpus. Musicians can adjust
the parameters to experiment with different harmonic idioms or rhythmic feels
while keeping the algorithm efficient and deterministic.
