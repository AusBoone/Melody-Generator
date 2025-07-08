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

While the algorithm is primarily heuristic, optional machine learning models can
subtly bias these choices. A lightweight LSTM predicts the next scale degree and
style embeddings derived from a variational autoencoder nudge the weights toward
specific genres. These components act as learned priors layered atop the
hand-crafted rules, providing a blend of determinism and data-driven variation.

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
   the harmony. The surrounding scale may change per chord (e.g., mixolydian on
   dominant chords) so non-chord tones outline the harmony more clearly.
5. **Weighted Selection** – Candidate notes are weighted by interval distance
   and whether they belong to the active chord. A small transition matrix
   biases the process toward stepwise motion, emulating learned probabilities.
6. **Interval Bias and Filters** – Large leaps are tracked so the next note is
   nudged in the opposite direction. Tritone jumps are removed unless no other
   options exist.
7. **Candidate Cache** – Source pools for each chord and octave are cached so
   note selection avoids rebuilding the same lists each iteration.
8. **Fallback Logic** – If no suitable note fits the current constraints a
   random scale tone is chosen to avoid stalls. This ensures every call returns
   a complete melody.
9. **Final Cadence** – The melody's last note is forced to the root of the
   final chord to provide a simple resolution.
10. **Optional Parts** – Additional helper functions create harmony lines,
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

**Caching and Dynamics**
Repeated conversions from note names to MIDI numbers are cached so the
algorithm scales linearly even for long melodies. Candidate note lists for each
chord are also cached per octave to avoid rebuilding them during every
iteration. MIDI velocities follow a crescendo then decrescendo curve and apply a
slight accent on downbeats so the phrase breathes like a real performance. A
``structure`` parameter lets callers repeat or vary sections (e.g. ``"AABA"``)
to create longer forms from smaller motifs.

**Markov Weights and Tritone Control**
Candidate weighting uses a small transition matrix favouring repeated pitches or
steps close to the previous interval. This Markov-style bias keeps motion
smooth while still allowing occasional leaps. The preferred scale for each chord
is cached, and the ``allow_tritone`` flag can suppress augmented fourth jumps
when a more consonant melody is desired.

These heuristics strike a balance between structured repetition and random
variation, yielding phrases that are musically coherent without relying on
complex theory.
From a data science perspective the rules serve as priors that encode stylistic
assumptions without the need for a large training corpus. Musicians can adjust
the parameters to experiment with different harmonic idioms or rhythmic feels
while keeping the algorithm efficient and deterministic.

## Recent Additions

- **Phrase Planning** – A high-level planning stage now sketches an octave
  range and tension curve before note generation. This ensures the melody rises
  and falls predictably across each phrase.
- **Hierarchical Phrase Planner** – ``PhrasePlanner`` first extracts bar-level
  anchor notes then infills surrounding notes with a repeating motif for
  improved long-term coherence.
- **Sequence Model Integration** – Candidate weights may be biased by a small
  LSTM trained on MIDI data for smoother motifs. The model implements the
  ``SequenceModel`` interface so alternative architectures can be swapped in.
  When PyTorch is unavailable the code falls back to heuristic weighting.
- **Style Embeddings** – A small VAE learns continuous style latents. Call
  ``set_style`` to activate a vector or ``interpolate_vectors`` to blend
  genres like Baroque, jazz and pop.
- **Independent Rhythm Engine** – Rhythmic patterns are produced by a dedicated
  :class:`RhythmGenerator` which models transitions between common note lengths.
  Onset times are generated first and melodies are fitted onto that skeleton.
- **Polyphonic Counterpoint** – ``PolyphonicGenerator`` runs four melody lines
  in parallel and adjusts them to avoid voice crossing before exporting to a
  multi-track MIDI file.
- **Harmonic Generator** – ``HarmonyGenerator`` predicts chord progressions
  and durations using a small BLSTM trained on lead-sheet data with
  Roman-numeral fallbacks when the model is unavailable. Chords align to
  downbeats detected in the rhythm skeleton.
- **Objective Feedback** – Generated phrases may be refined via Frechet Music
  Distance. Up to 5% of notes are randomly swapped when they reduce the
  distance to a small training corpus, encouraging more human-like melodies.
- **Data Augmentation & Transfer Learning** – ``augment_sequences`` provides
  transpositions, inversions and rhythm jitters for training data while
  ``fine_tune_model`` adapts the sequence model to genre-specific subsets.
- **Numba Optimizations** – Weight calculations run inside ``compute_base_weights``
  which is JIT-compiled with ``@njit`` when Numba is available. A ``profile``
  context manager based on ``cProfile`` helps inspect hot paths like
  ``pick_note``.
- **Vectorized Candidate Selection** – Candidate filtering and sampling now use
  NumPy broadcasting with ``numpy.random.choice`` when possible, eliminating
  Python-level loops for better performance.
- **Parallel Batch Generation** – Large exports use ``ProcessPoolExecutor`` and
  the web interface dispatches work to Celery so multiple melodies are created
  concurrently without blocking the UI.
- **Caching and Memoization** – ``scale_for_chord`` and ``note_to_midi`` are
  memoized with ``functools.lru_cache`` and candidate note pools are generated
  lazily on first use for faster selection.

## Candidate Weighting in Depth

Candidate selection is a weighted random draw. Each possible note begins with a
baseline weight derived from ``_TRANSITION_WEIGHTS`` based on the semitone
distance from the previous pitch. When the preceding interval is known,
``_SIMILARITY_WEIGHTS`` nudges the next step toward similar sizes, preserving
melodic contour. Chord tones on strong beats receive a 1.5x multiplier so the
harmony is emphasised.

If a :class:`melody_generator.phrase_planner.PhrasePlan` is provided, the
``tension_profile`` value for the current position biases weights via
``apply_tension_weights``. Higher tension encourages dissonant intervals, while
lower tension favours steps and repeated notes. All these calculations execute
with NumPy when available for speed.

Supplying a pretrained LSTM with ``sequence_model`` further shapes the melody.
The last few scale degrees feed into ``SequenceModel.predict_logits``; the
returned scores are added to candidate weights. When ``set_style`` provides a
style vector its values are added as an offset so genres like Baroque or jazz
subtly colour note choice.
Parallel fifths and octaves against the chord root are halved to maintain basic
counterpoint. Candidate weights also include a small bonus for contrary motion
and a penalty for repeated perfect fifth or octave leaps as determined by
``counterpoint_penalty``. After note generation an optional refinement step
computes the Frechet Music Distance (FMD) between the phrase and a small
training corpus. Up to five percent of notes are randomly replaced in a
hill-climbing loop and kept only when the FMD decreases, nudging melodies
toward the distribution of real music.

### ONNX Export and Quantization

The helper :func:`melody_generator.sequence_model.export_onnx` exports an LSTM
to ONNX format. :func:`melody_generator.sequence_model.quantize_onnx_model`
invokes ``onnxruntime.quantization.quantize_dynamic`` to produce an 8‑bit model
for CPU inference.  The exported model expects a sequence of scale‑degree
indices and outputs logits for the next degree, mirroring
``SequenceModel.predict_logits``.

## Putting It All Together

The heuristics outlined above are intentionally simple yet capture enough
structure to produce musically coherent phrases. When machine learning
extensions are enabled they act only as soft preferences, leaving the
deterministic backbone intact. This design keeps the system lightweight and
interpretable while still allowing researchers to experiment with more advanced
models.
