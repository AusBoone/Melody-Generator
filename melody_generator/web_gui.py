#!/usr/bin/env python3
"""Flask web interface for Melody Generator.

This module provides a minimal web front-end that mirrors the
functionality of the command line and Tkinter interfaces provided
by the :mod:`melody_generator` package. The goal is to expose the
melody generation functions over HTTP so users can experiment
directly from their browser.
"""

from __future__ import annotations

from importlib import import_module
import io
from tempfile import NamedTemporaryFile
from typing import List

from flask import Flask, render_template, request, flash
import base64
import os

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
generate_random_chord_progression = melody_generator.generate_random_chord_progression
generate_random_rhythm_pattern = melody_generator.generate_random_rhythm_pattern
generate_harmony_line = melody_generator.generate_harmony_line
generate_counterpoint_melody = melody_generator.generate_counterpoint_melody

# Create the Flask application instance and register templates and static files.
app = Flask(__name__, template_folder="templates", static_folder="static")
# Allow overriding the session secret via the environment for production use.
app.secret_key = os.environ.get("FLASK_SECRET", "change-me")


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the form and handle submissions.

    On ``GET`` the function simply renders the input form so the user can
    specify parameters for the melody generation.  When the form is
    submitted via ``POST`` a MIDI file is generated in memory and returned
    to the browser for immediate playback.
    """

    if request.method == 'POST':
        # Extract user selections, applying sensible defaults when
        # values are missing.
        key = request.form.get('key') or 'C'
        if key not in SCALE:
            flash("Invalid key selected. Please choose a valid key.")
            return render_template('index.html', scale=sorted(SCALE.keys()))

        bpm = int(request.form.get('bpm') or 120)
        timesig = request.form.get('timesig') or '4/4'
        notes = int(request.form.get('notes') or 16)
        motif_length = int(request.form.get('motif_length') or 4)
        harmony = bool(request.form.get('harmony'))
        random_rhythm = bool(request.form.get('random_rhythm'))
        counterpoint = bool(request.form.get('counterpoint'))
        harmony_lines = int(request.form.get('harmony_lines') or 0)

        # Determine the chord progression. The user may provide one
        # manually or tick the "random" box to generate it.
        if request.form.get('random_chords'):
            chords = generate_random_chord_progression(key)
        else:
            chords_str = request.form.get('chords', '')
            chords = [c.strip() for c in chords_str.split(',') if c.strip()]
            if not chords:
                chords = generate_random_chord_progression(key)
            # Validate that each supplied chord exists in the dictionary
            for chord in chords:
                if chord not in CHORDS:
                    flash(f"Unknown chord: {chord}")
                    return render_template('index.html', scale=sorted(SCALE.keys()))

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
            return render_template('index.html', scale=sorted(SCALE.keys()))

        if motif_length > notes:
            flash("Motif length cannot exceed the number of notes.")
            return render_template('index.html', scale=sorted(SCALE.keys()))
        melody = generate_melody(key, notes, chords, motif_length=motif_length)
        rhythm = generate_random_rhythm_pattern() if random_rhythm else None
        extra: List[List[str]] = []
        for _ in range(max(0, harmony_lines)):
            # Create as many harmony lines as requested
            extra.append(generate_harmony_line(melody))
        if counterpoint:
            extra.append(generate_counterpoint_melody(melody, key))

        # Write the MIDI data to a temporary file and return a page with
        # an embedded audio player so the user can immediately preview
        # the result in the browser. The temporary file is created with
        # ``delete=False`` so it can be reopened on Windows systems where
        # a file cannot be read while still open for writing.
        tmp = NamedTemporaryFile(suffix='.mid', delete=False)
        try:
            tmp_path = tmp.name
        finally:
            # Ensure the handle is closed immediately so the file can be
            # reopened by ``create_midi_file`` on all platforms.
            tmp.close()

        create_midi_file(
            melody,
            bpm,
            (numerator, denominator),
            tmp_path,
            harmony=harmony,
            pattern=rhythm,
            extra_tracks=extra,
        )

        # Read the generated MIDI data back into memory then delete the
        # temporary file.
        with open(tmp_path, 'rb') as fh:
            data = io.BytesIO(fh.read())
        os.remove(tmp_path)
        encoded = base64.b64encode(data.getvalue()).decode('ascii')
        return render_template('play.html', data=encoded)

    # On a normal GET request simply render the form so the user can
    # enter their parameters.
    return render_template('index.html', scale=sorted(SCALE.keys()))

# Allow the module to be run directly with ``python web_gui.py``.
# ``pragma: no cover`` keeps test coverage tools from complaining when
# this block is skipped during automated testing.
if __name__ == '__main__':  # pragma: no cover - manual usage
    # Launch the development server
    app.run(debug=True)
