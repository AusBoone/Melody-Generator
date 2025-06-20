# Melody-Generator
Python script that allows users to create a random melody in a specified key, with a specific BPM (beats per minute) and time signature. The generated melody can be saved as a MIDI file.

# Requirements
- Python 3.x
- mido (for MIDI generation)
- Flask (for the web interface)
- tkinter (for the GUI)

## Installing dependencies
Running `pip install .` will install these packages automatically. You can also
set them up manually with:

```bash
pip install -r requirements.txt
```

The tests stub out `mido`, `Flask` and `tkinter`, so they are not required to
run the test suite, but they are necessary for real use.

# Installation
Install the package from source:
```bash
pip install .
```

Once the project is published on PyPI you will be able to install it with:
```bash
pip install melody-generator
```

# Settings
User preferences such as BPM and key are stored in a JSON file located at
`~/.melody_generator_settings.json`. The GUI loads this file on startup and you
can choose to save your current selections after generating a melody.
You can override the location by setting the `MELODY_SETTINGS_FILE` environment
variable before starting the application.
Set the `MELODY_PLAYER` environment variable to a MIDI-capable application if the default player cannot handle `.mid` files. For example, `export MELODY_PLAYER=Music` on macOS or `set MELODY_PLAYER="C:\\Program Files\\Windows Media Player\\wmplayer.exe"` on Windows. The GUI's preview feature will then open files in that player instead of the system default.

# Usage

Below are step-by-step examples for the three ways of using the project.

### CLI

Generate a melody entirely from the command line:

```bash
melody-generator \
  --key C \
  --chords C,G,Am,F \
  --bpm 120 \
  --timesig 4/4 \
  --notes 16 \
  --output song.mid \
  --harmony --counterpoint --harmony-lines 1
```

This command creates `song.mid` with one harmony line and an additional counterpoint track.

### GUI

Simply run `melody-generator` with no arguments:

```bash
melody-generator
```

1. Choose a key, BPM, time signature and chord progression.
2. Check the **Harmony** or **Counterpoint** boxes to add extra tracks.
3. Click **Preview Melody** to hear the result without saving.
4. Click **Generate Melody** and select where to save the MIDI file.


### Web Interface

Start the Flask app:

```bash
python -m melody_generator.web_gui
```

1. Open `http://localhost:5000` in your browser.
2. Fill out the form just like the GUI version.
3. Submit to preview and download the generated file.
4. Set the `FLASK_SECRET` environment variable to a persistent secret. If it
   is not provided a random key is generated on startup and a warning is
   logged.
5. Optionally set `FLASK_DEBUG=1` to enable Flask debug mode during
   development.


## Docker Usage
Build the image and run the web interface:
```bash
docker build -t melody-generator .
docker run -p 5000:5000 melody-generator
```

The container launches the Flask server so you can open `http://localhost:5000`
and use the web interface without installing Python locally.

# Parameters
- **Key**: Enter the key for the melody (e.g., C, C#, Dm, etc.). Both major and minor keys are supported.
- **BPM**: Adjust the tempo using the slider (e.g., 120 BPM).
- **Time Signature**: Choose the time signature from the drop-down (e.g., 4/4, 3/4).
- **Number of notes**: Set how many notes to generate with the slider.
- **Harmony**: Tick this option to add a simple harmony line.
- **Counterpoint**: Generates an additional melody that moves against the main line.
- **Base Octave**: Starting octave for the melody. Use the slider or
  `--base-octave` flag to shift the register. Notes typically stay
  between this octave and the next higher one with rare octave shifts at
  phrase boundaries.

## CLI Flags
When running from the command line you can supply optional flags:
- `--random-chords N` generates a progression of `N` random chords and ignores `--chords`.
- `--random-rhythm` creates a random rhythmic pattern for the melody.
- `--harmony` adds a parallel harmony track.
- `--harmony-lines N` creates `N` additional harmony parts.
- `--counterpoint` generates a contrapuntal line based on the melody.
- `--base-octave N` sets the starting octave of the melody (default: 4).

## Development

Run the automated test suite with `pytest`:

```bash
pytest
```

External dependencies such as `mido` and `tkinter` are stubbed out in the tests
so they do not need to be installed in order to run them.

Lint the project using [ruff](https://github.com/astral-sh/ruff):

```bash
ruff check .
```

To build the Docker image locally run:

```bash
docker build -t melody-generator .
```

If this command fails with `command not found`, install Docker or use an
alternative container runtime such as Podman.

# New Features

- Automatic chord progressions based on common pop patterns.
- Expanded rhythmic patterns including eighth- and sixteenth-note figures.
- Melodic rules such as leap compensation to avoid jarring jumps.
- Variations when motifs repeat so phrases remain interesting.
- Additional modes like Dorian, Mixolydian and pentatonic scales.
- Dynamic velocity in the MIDI output for a more natural sound.
- GUI button to reload saved preferences at any time.
- GUI can preview the generated melody before saving.
- Web interface now previews the generated MIDI using an inline player.
- Harmony and counterpoint tracks for multi-line melodies.
- Optional base octave parameter to constrain the melody's register with
  occasional octave shifts.

## Algorithm Overview

The library creates melodies using a short motif that repeats
throughout the phrase.  Each subsequent note is chosen from the current
chord and biased toward small intervals from the previous pitch.  Large
leaps are tracked so the next note compensates by moving in the
opposite direction.  When no suitable candidate exists a random pitch
from the key acts as a safe fallback.  Rhythm can either be selected
from a library of common patterns or generated randomly.
