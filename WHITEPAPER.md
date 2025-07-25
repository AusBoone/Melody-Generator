# Melody-Generator Whitepaper

Melody-Generator is a lightweight yet extensible toolchain for algorithmically
constructing short musical ideas.  This paper summarises how each piece of the
system fits together, the principles behind the core algorithms and the optional
machine‑learning extensions.  Detailed guides live in the `docs/` directory.

## System Architecture

The codebase is a conventional Python package named `melody_generator`.  Modules
are grouped by responsibility so every step – from command-line parsing through
MIDI file creation – can be reused programmatically.

- **CLI and Interfaces** – `cli.py`, `gui.py` and `web_gui.py` expose the
  command-line, desktop and web entry points.  Each interface validates
  arguments and forwards them to the generation engine.
- **Core Engine** – `phrase_planner.py`, `melody.py` and helpers such as
  `rhythm_engine.py`, `harmony_generator.py` and `voice_leading.py` implement
  the rule-based generation algorithm.  The engine purposely avoids heavy
  dependencies so it can run on any platform.  A full breakdown of the
  heuristics appears in [`docs/README_ALGORITHM.md`](docs/README_ALGORITHM.md).
- **Machine Learning Extensions** – Optional modules `sequence_model.py`,
  `style_embeddings.py` and `tension.py` provide predictive probabilities,
  style vectors and tension curves that bias the otherwise deterministic rules.
  Concepts behind these modules are explained in
  [`docs/README_ML_CONCEPTS.md`](docs/README_ML_CONCEPTS.md).
- **MIDI I/O and Playback** – `midi_io.py` writes Standard MIDI files and
  interfaces with FluidSynth for preview.  Static templates and assets power the
  Flask-based web UI.
### Modules at a Glance

- `batch_generation.py` – spawn multiple melodies in parallel for dataset creation.
- `augmentation.py` – data augmentation and fine-tuning helpers.
- `performance.py` – core weighting logic and profiling tools.
- `polyphony.py` – manages multi-voice counterpoint generation.
- `playback.py` – preview MIDI files via FluidSynth.
- `feedback.py` – Frechet Music Distance scoring and refinement.
- `dynamics.py` – velocity and timing humanization.
- `templates/` and `static/` – HTML assets for the web UI.


### Project Layout

- `melody_generator/` contains the Python package with all modules
- `scripts/` holds setup and build helpers
- `docs/` houses extended guides referenced in this paper
- `tests/` includes the PyTest suite and sample MIDI files
- `examples/` (if present) shows quick demo scripts

A simplified overview of the runtime flow is illustrated below.

```
+-----------+     +-----------------+     +-------------+
|  CLI/GUI  | --> | Generation Core | --> |  MIDI File  |
+-----------+     +-----------------+     +-------------+
                                      \-> Playback (optional)
```

Extensive unit tests reside in `tests/` and `ruff` enforces PEP8 style via
`ruff.toml`.  Setup scripts under `scripts/` install dependencies on each
platform.

## Key Algorithms

The fundamental routine `generate_melody` constructs a motif and repeats it while
respecting the chord progression and rhythm pattern.  At each step candidate
notes are drawn from the current chord and scale, then weighted according to
interval distance, prior context and optional ML hints.

```
motif = generate_motif(motif_length, key)
pattern = choose_rhythm()  # or user‑supplied
for index in range(num_notes):
    chord = chord_progression[index % len(chord_progression)]
    allowed = restrict_to_chord(key, chord)
    next_note = pick_note(allowed, previous, leap_info)
    melody.append(next_note)
    update_leap_info()
```

Large leaps trigger compensating motion so phrases maintain a natural contour.
If no candidate satisfies the constraints a fallback selects a random scale tone
so the melody always continues.  Harmony lines, counterpoint and chord tracks use
the same logic but operate on separate voices.

### Detailed Algorithm Flow
1. **Initialisation** – motif and rhythm pattern are generated or loaded from user input.
2. **Per-note Loop** – for each step the current chord restricts allowable scale degrees and a weighting function ranks candidates.
3. **Leap Tracking** – large intervals are recorded so the next choice favours contrary motion.
4. **Fallback Handling** – when weights collapse to zero a random scale tone is emitted.
5. **Cadence Enforcement** – the final note resolves to the tonic of the last chord for a clear ending.
During step 2 the candidate pool is built from cached scale and chord notes using `_candidate_pool`. Weights begin with `compute_base_weights` and are adjusted by style embeddings, sequence model logits and the current tension target. Counterpoint helpers penalise parallel fifths or octaves. NumPy accelerates these calculations when available.

## Algorithm Complexity

The core generation loop performs a constant amount of work for each produced
note. Candidate pools are cached per chord and octave so the selection step does
not rebuild lists on every iteration. As a result the algorithm runs in
**O(n)** time where *n* is the number of notes requested. Phrase planning and
post-processing steps scale with the number of bars, typically a small constant
factor. Memory usage remains linear with the melody length since only a history
of recent notes is retained.

Although the overall complexity is linear, the constant factors matter in
practice. Let *c* represent the average number of candidate pitches examined
per step. The weighting procedure consults style embeddings, neural logits and
voice-leading heuristics, yielding a per-note cost of roughly *O(c)*. Because
`c` rarely exceeds a few dozen values, the approach remains tractable even when
generating multi-minute phrases. Polyphonic generation duplicates this cost for
each active voice, so a four-part texture is still **O(n)** but with a factor of
four in both time and memory. The design intentionally avoids quadratic
behaviour so that the generator scales to longer compositions without requiring
specialised hardware.

```text
for i in range(n):
    chord = progression[i % len(progression)]
    candidates = cached_pool[chord]
    next_note = weighted_choice(candidates)
    melody.append(next_note)
```

## Machine Learning Components

Neural models are optional yet integrate tightly with the heuristic pipeline.

- **Sequence Model** – An LSTM or compatible architecture exposes
  `predict_logits(history)` to obtain probabilities for the next scale degree.
  These logits adjust the note weights before sampling.
- **Style Embeddings** – A variational autoencoder produces compact style
  vectors.  Setting an active vector biases selection toward that genre and
  embeddings can be loaded from JSON (`docs/example_styles.json`).
- **Tension Estimation** – Interval‑based heuristics compute a real‑valued
  tension curve.  When NumPy is available the calculation is vectorised.  The
  tension profile modulates note weights so melodies ebb and flow like a human
  performance.
- **ONNX Export** – Utilities convert trained models to ONNX and apply
  dynamic quantisation for deployment without full PyTorch.

Utility functions in `augmentation.py` demonstrate how to fine-tune these models on custom MIDI sequences. The lightweight design runs on modest hardware, and you can replace the architecture by implementing the `SequenceModel` protocol.

## Phrase Planning and Pitch Range Control

High-level structure originates in `phrase_planner.py`. The
`generate_phrase_plan` helper sketches a pitch range and tension curve before
any notes are produced. Each `PhrasePlan` contains a `tension_profile` list and
`(min_octave, max_octave)` tuple validated against `MIN_OCTAVE` and `MAX_OCTAVE`
from `__init__.py`. The `PhrasePlanner` class then identifies anchor points with
`plan_skeleton` and fills the gaps using `infill_skeleton`. This hierarchical
planning keeps phrases within a defined register while allowing local weighting
heuristics to operate freely.

## Polyphonic Generation and Voice Leading

`polyphony.PolyphonicGenerator` manages four independent voices. Each part can
use its own `SequenceModel`, after which `_enforce_voice_leading` shifts notes by
octave to avoid crossing and ensures neighbouring voices remain within a single
octave. The corrections rely on the interval checks implemented in
`voice_leading.py` so counterpoint stays clean.

## Training and Fine Tuning

Although pretrained weights are not included, `augmentation.py` provides dataset
helpers such as `augment_sequences` for transposition and inversion. The
`fine_tune_model` routine demonstrates teacher forcing in PyTorch so
`SequenceModel` or `StyleVAE` variants can adapt to genre-specific material.

## Dataset Preparation and Evaluation Metrics

`batch_generation.py` automates dataset creation by repeatedly calling
`generate_melody`. Resulting phrases are assessed with Frechet Music Distance
(FMD) via `feedback.py`. `compute_fmd` measures divergence from a reference set
while `refine_with_fmd` slightly alters notes when it reduces the distance.
These metrics provide an objective gauge when experimenting with new models or
heuristics.

### Recommended Pipeline

1. **Collect MIDI files** from public datasets such as the Lakh corpus or
   user-generated material.
2. **Convert** each file to a sequence of scale degrees with
   `midi_to_degrees` and align rhythms to the nearest 16th note.
3. **Filter** out fragments shorter than eight bars or containing unsupported
   time signatures.
4. **Augment** the remaining sequences using `augment_sequences` to apply
   transpositions and rhythmic jitter.
5. **Split** the data into training and validation sets before feeding them to
   `fine_tune_model` or another `SequenceModel` implementation.

```text
for midi in corpus:
    degrees = midi_to_degrees(midi)
    if len(degrees) < threshold:
        continue
    for seq in augment_sequences(degrees):
        write_to_dataset(seq)
```

This process yields a balanced collection of melodies in a uniform format,
ready for training lightweight models that bias note selection.

When constructing a large corpus it is beneficial to maintain provenance
metadata. Keeping track of the original source, applied augmentations and any
manual corrections aids reproducibility and allows subsets to be reconstructed
for ablation studies. A typical workflow writes an index file alongside the
preprocessed sequences that records these details in JSON:

```text
{
    "src": "lakh/1234.mid",
    "transposition": 2,
    "stretch": 1.0,
    "valid_bars": 12
}
```

Researchers may then implement stratified sampling or k-fold cross validation
directly on this metadata, ensuring each experiment draws from comparable
distributions. Where licensing permits, sharing these indices rather than raw
MIDI files simplifies collaboration while respecting copyright.

## Usage Examples

Command‑line invocation is the most common entry point.  See `README.md` for a
full option list.

```bash
melody-generator --key C --chords C,G,Am,F --bpm 120 \
    --timesig 4/4 --notes 16 --output song.mid
```

The desktop GUI (`python -m melody_generator.gui`) and web UI
(`python -m melody_generator.web_gui`) expose the same parameters.  Advanced
users may also call the library directly:

```python
from melody_generator import generate_melody, create_midi_file
notes = generate_melody(key="Am", chords=["Am", "F", "C", "G"], notes=32)
create_midi_file("song.mid", notes)
```
```python
import melody_generator as mg

# Custom note selection that always picks the highest weighted pitch
def greedy_pick(candidates, weights):
    return candidates[weights.index(max(weights))]

mg.pick_note = greedy_pick
melody = mg.generate_melody("Am", 32, ["Am", "F", "C", "G"])
mg.create_midi_file("deterministic.mid", melody)
```
Users can customise note weighting by writing their own `pick_note` function and passing it to `generate_melody`. This flexibility lets researchers test new heuristics without rewriting the rest of the pipeline.
Consult [`docs/README_SETUP.md`](docs/README_SETUP.md) for dependency
installation and [`docs/README_SOUND_FONTS.md`](docs/README_SOUND_FONTS.md) for
SoundFont resources.

## Further Reading

- [`docs/README_ALGORITHM.md`](docs/README_ALGORITHM.md) explains the algorithms
  in depth and includes additional pseudocode.
- [`docs/README_ML_CONCEPTS.md`](docs/README_ML_CONCEPTS.md) covers the neural
  extensions in greater detail.
- [`docs/README_MUSICAL_OVERVIEW.md`](docs/README_MUSICAL_OVERVIEW.md) offers a
  short guide aimed at classically trained musicians.
- [`docs/README_FLUIDSYNTH.md`](docs/README_FLUIDSYNTH.md) describes how to
  install the FluidSynth dependency.

## Security Considerations

Melody‑Generator performs all processing locally and does not require network
access once dependencies are installed. Nevertheless you should treat any
downloaded MIDI files with caution, as they may embed unusual metadata. The
loader strips non-MIDI chunks to prevent file parsing issues. If using the web
interface, run it on ``localhost`` and avoid exposing it to the public internet
without additional authentication and rate limiting.

From a security engineering standpoint the most likely attack vector involves
malicious MIDI files crafted to exploit parser vulnerabilities. The project
therefore opens files in binary mode and validates chunk headers before
processing any events. Paths supplied on the command line are resolved to their
canonical forms to mitigate directory traversal attacks. Users embedding the
library within larger applications should apply the principle of least
privilege—read-only filesystem permissions and sandboxing where practical—to
isolate the generation process from sensitive data. None of the components need
elevated privileges, so dropping capabilities is recommended when launching the
web interface as a long-running service.

## Design Considerations and Extensibility

The algorithms assume monophonic melodies built from Western scales and simple triads. Chord symbols are interpreted using basic pop conventions rather than full jazz voicings. Every function is designed for easy replacement if you wish to experiment with alternate theory rules or microtonal scales. Modular weighting hooks make it straightforward to plug in additional ML models or custom heuristics.


This whitepaper provides a high-level orientation only.  The project combines
simple rule-based methods with optional machine learning to remain approachable
while enabling more advanced exploration.
