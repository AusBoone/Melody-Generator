# Melody-Generator
Melody-Generator is a research-oriented project that provides a simple yet versatile engine for
generating melodies in any key, tempo and meter. The output can be rendered to a standard MIDI
file for use in digital audio workstations. For a formal exposition of the algorithm see
[README_ALGORITHM.md](README_ALGORITHM.md).

# Requirements
- Python 3.x
- mido (for MIDI generation)
- Flask (for the web interface)
- tkinter (for the GUI)

## Installing dependencies
Running `pip install .` will install these packages automatically. For
development, an editable install is available:

```bash
pip install -e .
```

You can also set up the dependencies manually with:

```bash
pip install -r requirements.txt
```
### Quick setup on macOS

Run the helper script to install Homebrew packages and Python
dependencies. The script checks for an existing ``python3``
installation and only installs a new version when the current one is
older than 3.8. A virtual environment is created under ``./venv``.

```bash
./setup_mac.sh
```

After it completes activate the environment with
`source venv/bin/activate` to start using ``melody-generator``.
PyFluidSynth wraps the FluidSynth library which must be installed separately.
Install the system package with `apt-get install fluidsynth` on Debian-based Linux or `brew install fluid-synth` on macOS.
Without FluidSynth the preview button and web playback will fail.

Tkinter powers the GUI and may need to be installed manually, e.g. `apt-get install python3-tk` on Debian-derived systems.
For audio playback a General MIDI soundfont such as the optional `fluid-soundfont-gm` package is recommended.
On platforms without a prebuilt PyFluidSynth wheel you might also need the Fluidsynth development headers: `apt-get install libfluidsynth-dev`.

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
Set `SOUND_FONT` to the path of a SoundFont file (``.sf2``) to enable the built-in
FluidSynth playback used by the GUI and web interface. The desktop GUI also
provides a **SoundFont** field so you can browse to a file at runtime. If not
provided the application tries a common system location such as
``/usr/share/sounds/sf2/TimGM6mb.sf2``. When neither FluidSynth nor a usable
soundfont is available the preview buttons fall back to your operating system's
default MIDI player.

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
  --instrument 0 \
  --soundfont /path/to/font.sf2 \
  --output song.mid \
  --harmony --counterpoint --harmony-lines 1
```

This command creates `song.mid` with one harmony line and an additional counterpoint track.
The `--instrument` option selects the General MIDI program number used for the melody.
Use `--play` to automatically preview the file once it is written.

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
  `--base-octave` flag to shift the register. Allowed range is **0-8** so
  all generated notes remain within the MIDI specification. Notes
  typically stay between this octave and the next higher one with rare
  octave shifts at phrase boundaries.

## CLI Flags
When running from the command line you can supply optional flags:
- `--random-chords N` generates a progression of `N` random chords and ignores `--chords`.
- `--random-rhythm` creates a random rhythmic pattern for the melody.
- `--harmony` adds a parallel harmony track.
- `--harmony-lines N` creates `N` additional harmony parts.
- `--counterpoint` generates a contrapuntal line based on the melody.
- `--base-octave N` sets the starting octave of the melody (0-8,
  default: 4).
- `--play` previews the resulting MIDI file using FluidSynth when available and
  falls back to the system player otherwise.
- `--soundfont PATH` uses the specified SoundFont when playing the file with
  `--play`.

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
The linter is configured via `ruff.toml`, which enforces a 100 character
line length and targets Python 3.8. Adjust this file if different rules
are required.

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
- Web interface now previews the generated melody using a WAV rendering
  created with FluidSynth.
- Harmony and counterpoint tracks for multi-line melodies.
- Optional base octave parameter to constrain the melody's register with
  occasional octave shifts.

## Algorithm Overview

The generator begins with a short motif which is reiterated across the phrase in
slightly varied form. Candidate notes for each position are drawn from the
current chord and proximate scale degrees, forming a small search space that
reflects traditional voice-leading practice. Intervals are weighted inversely by
size so the melody favors stepwise motion. Large leaps are recorded and the next
note is gently pulled toward the prior tessitura to avoid abrupt contours. When
no candidate satisfies the constraints, the algorithm defaults to a uniform
choice from the key, ensuring progress. Rhythm can be sampled from a corpus of
common patterns or generated stochastically. A detailed exposition of these
heuristics is available in [README_ALGORITHM.md](README_ALGORITHM.md).
