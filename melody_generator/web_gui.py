#!/usr/bin/env python3
"""Flask web interface for Melody Generator.

This module provides a minimal web front-end that mirrors the
functionality of the command line and Tkinter interfaces provided
by the :mod:`melody_generator` package.  Users can select a key,
chord progression and tempo through a simple HTML form.  The server
generates a temporary MIDI file which is returned for download and,
when possible, rendered to WAV for immediate playback.

The interface is intentionally lightweight and runs with Flask's
development server so examples can be tried without additional
infrastructure.
"""
# This revision introduces validation for the ``base_octave`` input so
# out-of-range values (anything not between ``MIN_OCTAVE`` and
# ``MAX_OCTAVE``) trigger a flash message instead of causing errors when
# generating the melody.
# The original implementation attempted to render the generated MIDI to WAV
# using FluidSynth so that browsers lacking MIDI support could preview the
# melody. This update flashes an informative message when that rendering
# fails because either FluidSynth itself or a compatible SoundFont is missing.
# The play template now displays flash messages so users are aware that the
# preview audio is unavailable.
#
# The current update extends the form with options to enable machine-learning
# based weighting and to choose a predefined style embedding. When the user
# activates these features but required dependencies such as PyTorch are not
# installed, the view now flashes a clear error instead of returning a server
# error.
#
# This revision also ensures Celery tasks receive keyword arguments. The
# ``index`` view now dispatches ``generate_preview_task`` using
# ``delay(**params)`` so that asynchronous workers get the same named
# parameters as the synchronous path.
#
# This update also detects Celery broker connection failures. When a
# ``delay`` call cannot reach the broker the exception is logged and the
# preview is generated synchronously so the request still succeeds.

from __future__ import annotations

from importlib import import_module
from tempfile import NamedTemporaryFile
from typing import List

from melody_generator import playback
from melody_generator.playback import MidiPlaybackError

try:
    from celery import Celery
except Exception:  # pragma: no cover - optional dependency
    Celery = None

from flask import Flask, render_template, request, flash
import base64
import os
import secrets
import logging

# Import the core melody generation package dynamically so the
# Flask app can live in a separate module without circular imports.
melody_generator = import_module("melody_generator")

# Pull the functions and data structures we need from the loaded module.
# Doing this makes the rest of the code look as if we had imported them
# normally with ``from melody_generator import ...``.
generate_melody = melody_generator.generate_melody
create_midi_file = melody_generator.create_midi_file
SCALE = melody_generator.SCALE
CHORDS = melody_generator.CHORDS
canonical_key = melody_generator.canonical_key
canonical_chord = melody_generator.canonical_chord
generate_random_chord_progression = melody_generator.generate_random_chord_progression
generate_random_rhythm_pattern = melody_generator.generate_random_rhythm_pattern
generate_harmony_line = melody_generator.generate_harmony_line
generate_counterpoint_melody = melody_generator.generate_counterpoint_melody
MIN_OCTAVE = melody_generator.MIN_OCTAVE
MAX_OCTAVE = melody_generator.MAX_OCTAVE
load_sequence_model = melody_generator.load_sequence_model
STYLE_VECTORS = melody_generator.style_embeddings.STYLE_VECTORS
get_style_vector = melody_generator.style_embeddings.get_style_vector

INSTRUMENTS = {
    "Piano": 0,
    "Guitar": 24,
    "Bass": 32,
    "Violin": 40,
    "Flute": 73,
}

# Create the Flask application instance and register templates and static files.
app = Flask(__name__, template_folder="templates", static_folder="static")

logger = logging.getLogger(__name__)

# Configure the session secret.
secret = os.environ.get("FLASK_SECRET")
if not secret:
    secret = secrets.token_urlsafe(32)
    logger.warning(
        "FLASK_SECRET environment variable not set. "
        "Using a randomly generated key; sessions will not persist across restarts."
    )
app.secret_key = secret

# Optional Celery application used to offload melody rendering so the
# Flask thread remains responsive. The broker defaults to the in-memory
# backend which requires no external services for small deployments.
celery_app = None
if Celery is not None:
    celery_app = Celery(
        __name__, broker=os.environ.get("CELERY_BROKER_URL", "memory://")
    )


def _generate_preview(
    key: str,
    bpm: int,
    timesig: tuple[int, int],
    notes: int,
    motif_length: int,
    base_octave: int,
    instrument: str,
    harmony: bool,
    random_rhythm: bool,
    counterpoint: bool,
    harmony_lines: int,
    include_chords: bool,
    chords_same: bool,
    enable_ml: bool,
    style: str | None,
    chords: List[str],
    humanize: bool,
) -> tuple[str, str]:
    """Return ``(audio_b64, midi_b64)`` for the requested melody."""

    seq_model = None
    if enable_ml:
        try:
            seq_model = load_sequence_model(None, len(SCALE[key]))
        except RuntimeError as exc:
            # Propagate dependency errors so the caller can display a message
            raise RuntimeError(str(exc)) from exc

    melody = generate_melody(
        key,
        notes,
        chords,
        motif_length=motif_length,
        base_octave=base_octave,
        sequence_model=seq_model,
        style=style or None,
    )
    rhythm = generate_random_rhythm_pattern() if random_rhythm else None
    extra: List[List[str]] = []
    for _ in range(max(0, harmony_lines)):
        extra.append(generate_harmony_line(melody))
    if counterpoint:
        extra.append(generate_counterpoint_melody(melody, key))

    tmp = NamedTemporaryFile(suffix=".mid", delete=False)
    try:
        tmp_path = tmp.name
    finally:
        tmp.close()

    numerator, denominator = timesig
    create_midi_file(
        melody,
        bpm,
        (numerator, denominator),
        tmp_path,
        harmony=harmony,
        pattern=rhythm,
        extra_tracks=extra,
        chord_progression=chords if include_chords else None,
        chords_separate=not chords_same,
        program=INSTRUMENTS.get(instrument, 0),
        humanize=humanize,
    )

    wav_tmp = NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        wav_path = wav_tmp.name
    finally:
        wav_tmp.close()

    try:
        playback.render_midi_to_wav(tmp_path, wav_path)
    except MidiPlaybackError:
        wav_data = None
    else:
        with open(wav_path, "rb") as fh:
            wav_data = fh.read()
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    with open(tmp_path, "rb") as fh:
        midi_bytes = fh.read()
    os.remove(tmp_path)

    audio_encoded = base64.b64encode(wav_data).decode("ascii") if wav_data else ""
    midi_encoded = base64.b64encode(midi_bytes).decode("ascii")
    return audio_encoded, midi_encoded


if celery_app is not None:
    generate_preview_task = celery_app.task(_generate_preview)  # type: ignore


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the form and handle submissions.

    On ``GET`` the function simply renders the input form so the user can
    specify parameters for the melody generation. When submitted via ``POST``
    a MIDI file is generated in memory and returned to the browser.

    @returns Response: Rendered template or audio playback page.
    """

    if request.method == 'POST':
        # Extract user selections, applying sensible defaults when
        # values are missing.
        key = request.form.get('key') or 'C'
        try:
            key = canonical_key(key)
        except ValueError:
            flash("Invalid key selected. Please choose a valid key.")
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        bpm = int(request.form.get('bpm') or 120)
        timesig = request.form.get('timesig') or '4/4'
        notes = int(request.form.get('notes') or 16)
        motif_length = int(request.form.get('motif_length') or 4)
        base_octave = int(request.form.get('base_octave') or 4)
        instrument = request.form.get('instrument') or 'Piano'
        # Validate the selected instrument against the known General MIDI
        # mapping. Unknown values likely mean the form was tampered with.
        if instrument not in INSTRUMENTS:
            flash("Unknown instrument")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )
        harmony = bool(request.form.get('harmony'))
        random_rhythm = bool(request.form.get('random_rhythm'))
        counterpoint = bool(request.form.get('counterpoint'))
        harmony_lines = int(request.form.get('harmony_lines') or 0)
        include_chords = bool(request.form.get('include_chords'))
        chords_same = bool(request.form.get('chords_same'))
        humanize = bool(request.form.get('humanize', '1'))
        enable_ml = bool(request.form.get('enable_ml'))
        style = request.form.get('style') or None

        # Determine the chord progression. The user may provide one
        # manually or tick the "random" box to generate it.
        if request.form.get('random_chords'):
            chords = generate_random_chord_progression(key)
        else:
            chords_str = request.form.get('chords', '')
            chord_names = [c.strip() for c in chords_str.split(',') if c.strip()]
            if not chord_names:
                chords = generate_random_chord_progression(key)
            else:
                chords = []
                for chord in chord_names:
                    try:
                        chords.append(canonical_chord(chord))
                    except ValueError:
                        flash(f"Unknown chord: {chord}")
                        return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        try:
            parts = timesig.split('/')
            if len(parts) != 2:
                raise ValueError
            numerator, denominator = map(int, parts)
            if numerator <= 0 or denominator <= 0:
                raise ValueError
        except ValueError:
            flash(
                "Time signature must be two integers in the form 'numerator/denominator' with numerator > 0 and denominator > 0."
            )
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        if motif_length > notes:
            flash("Motif length cannot exceed the number of notes.")
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        if not MIN_OCTAVE <= base_octave <= MAX_OCTAVE:
            flash(
                f"Base octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}."
            )
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        if style:
            try:
                get_style_vector(style)
            except KeyError:
                flash(f"Unknown style: {style}")
                return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        params = dict(
            key=key,
            bpm=bpm,
            timesig=(numerator, denominator),
            notes=notes,
            motif_length=motif_length,
            base_octave=base_octave,
            instrument=instrument,
            harmony=harmony,
            random_rhythm=random_rhythm,
            counterpoint=counterpoint,
            harmony_lines=harmony_lines,
            include_chords=include_chords,
            chords_same=chords_same,
            humanize=humanize,
            enable_ml=enable_ml,
            style=style,
            chords=chords,
        )

        try:
            if celery_app is not None:
                try:
                    # ``delay`` passes the parameters to the Celery worker using
                    # keyword arguments so the task receives the same structure as
                    # the direct function call. Connection failures fall back to
                    # synchronous generation so the request still completes.
                    result = generate_preview_task.delay(**params).get()
                except Exception:  # pragma: no cover - triggered via tests
                    logger.exception(
                        "Celery broker unavailable; running preview synchronously"
                    )
                    result = _generate_preview(**params)
            else:
                # Execute synchronously when Celery is unavailable.
                result = _generate_preview(**params)
        except RuntimeError as exc:
            flash(str(exc))
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        audio_encoded, midi_encoded = result
        if not audio_encoded:
            flash(
                "Preview audio could not be generated because FluidSynth or a soundfont is unavailable."
            )
        return render_template('play.html', audio=audio_encoded, midi=midi_encoded)

    # On a normal GET request simply render the form so the user can
    # enter their parameters.
    return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

# Allow the module to be run directly with ``python web_gui.py``.
# ``pragma: no cover`` keeps test coverage tools from complaining when
# this block is skipped during automated testing.
if __name__ == '__main__':  # pragma: no cover - manual usage
    # Launch the development server
    if os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}:
        app.debug = True
    app.run()
