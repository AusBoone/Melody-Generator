#!/usr/bin/env python3
"""Flask web interface for Melody Generator.

This module provides a minimal web front-end that mirrors the
functionality of the command line and Tkinter interfaces in
``melody-generator.py``. The goal is to expose the melody
generation functions over HTTP so users can experiment directly
from their browser.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from flask import Flask, render_template, request
import base64

# Dynamically load ``melody-generator.py`` so we can reuse its
# melody creation functions without duplicating code. ``spec_from_file_location``
# allows importing a module from an arbitrary path.
MODULE_PATH = Path(__file__).resolve().parent / "melody-generator.py"
spec = importlib.util.spec_from_file_location("melody_generator", MODULE_PATH)
melody_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(melody_generator)

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


@app.route('/', methods=['GET', 'POST'])
def index():
    """Handle the main form for GET and POST requests."""

    if request.method == 'POST':
        # Extract user selections, applying sensible defaults when
        # values are missing.
        key = request.form.get('key') or 'C'
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

        numerator, denominator = map(int, timesig.split('/'))
        melody = generate_melody(key, notes, chords, motif_length=motif_length)
        rhythm = generate_random_rhythm_pattern() if random_rhythm else None
        extra: List[List[str]] = []
        for _ in range(max(0, harmony_lines)):
            extra.append(generate_harmony_line(melody))
        if counterpoint:
            extra.append(generate_counterpoint_melody(melody, key))

        # Write the MIDI data to a temporary file and return a page with
        # an embedded audio player so the user can immediately preview
        # the result in the browser.
        with NamedTemporaryFile(suffix='.mid') as tmp:
            create_midi_file(
                melody,
                bpm,
                (numerator, denominator),
                tmp.name,
                harmony=harmony,
                pattern=rhythm,
                extra_tracks=extra,
            )
            tmp.seek(0)
            data = io.BytesIO(tmp.read())
        encoded = base64.b64encode(data.getvalue()).decode('ascii')
        return render_template('play.html', data=encoded)

    # On a normal GET request simply render the form so the user can
    # enter their parameters.
    return render_template('index.html', scale=sorted(SCALE.keys()))

# Allow the module to be run directly with ``python web_gui.py``.
# ``pragma: no cover`` keeps test coverage tools from complaining when
# this block is skipped during automated testing.
if __name__ == '__main__':  # pragma: no cover - manual usage
    app.run(debug=True)
