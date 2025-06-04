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

from flask import Flask, render_template_string, request, send_file

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

# Create the Flask application instance.
app = Flask(__name__)

# Minimal HTML template for the web form. The template syntax is
# rendered with ``render_template_string`` below to keep this file
# self-contained. In a real application you might use separate
# template files instead.
FORM_HTML = """
<!doctype html>
<title>Melody Generator</title>
<h1>Generate Melody</h1>
<form method="post">
  Key:
  <select name="key">
    {% for k in scale %}<option value="{{k}}">{{k}}</option>{% endfor %}
  </select><br>
  Chord progression (comma separated):<br>
  <input name="chords"><br>
  <label><input type="checkbox" name="random_chords" value="1"> Random chords</label><br>
  BPM: <input type="number" name="bpm" value="120"><br>
  Time Signature: <input name="timesig" value="4/4"><br>
  Number of notes: <input type="number" name="notes" value="16"><br>
  Motif length: <input type="number" name="motif_length" value="4"><br>
  <label><input type="checkbox" name="harmony" value="1"> Harmony</label><br>
  <label><input type="checkbox" name="random_rhythm" value="1"> Random rhythm</label><br>
  <input type="submit" value="Generate">
</form>
"""

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

        # Write the MIDI data to a temporary file, then stream it
        # back to the client as a download.
        with NamedTemporaryFile(suffix='.mid') as tmp:
            create_midi_file(
                melody,
                bpm,
                (numerator, denominator),
                tmp.name,
                harmony=harmony,
                pattern=rhythm,
            )
            tmp.seek(0)
            data = io.BytesIO(tmp.read())
        data.seek(0)
        # ``send_file`` streams the BytesIO object back to the browser so
        # the user can save the generated MIDI file.
        return send_file(
            data,
            mimetype='audio/midi',
            as_attachment=True,
            download_name='melody.mid',
        )

    # On a normal GET request simply render the form so the user can
    # enter their parameters.
    return render_template_string(FORM_HTML, scale=sorted(SCALE.keys()))

# Allow the module to be run directly with ``python web_gui.py``.
# ``pragma: no cover`` keeps test coverage tools from complaining when
# this block is skipped during automated testing.
if __name__ == '__main__':  # pragma: no cover - manual usage
    app.run(debug=True)
