# Melody-Generator
Melody-Generator is a research-oriented project that provides a simple yet versatile engine for
generating melodies in any key, tempo and meter. The output can be rendered to a standard MIDI
file for use in digital audio workstations. For a formal exposition of the algorithm see
[docs/README.md](docs/README.md).

## Documentation

The [docs/README.md](docs/README.md) index links to the algorithm description,
setup guide, FluidSynth notes and soundfont resources. Separate guides cover
the machine learning components used for style embeddings and sequence models
([docs/README_ML_CONCEPTS.md](docs/README_ML_CONCEPTS.md)) and offer a brief
musician's perspective
([docs/README_MUSICAL_OVERVIEW.md](docs/README_MUSICAL_OVERVIEW.md)).

## Getting Started

1. **Download the project**
   - Clone it with `git clone https://github.com/AusBoone/Melody-Generator.git`.
   - Or select **Code → Download ZIP** on GitHub and extract the archive.
2. **Open a terminal** and change into the directory:

   ```bash
   cd Melody-Generator
   ```

3. **Create a virtual environment** (optional but recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use .venv\Scripts\activate
   ```

4. **Install the package and its dependencies**:

   ```bash
   pip install .
   ```

5. **Launch the graphical interface** with the installed command:

   ```bash
   melody-generator
   ```

   If the command is not found, ensure your environment's `bin` directory is on
   your `PATH`.

   If you prefer running directly from the source without installation, use:

   ```bash
   python -m melody_generator
   ```

   Run this from the **project root** so Python locates the package correctly.

   Avoid executing `python melody_generator.py` because the package must be run
   as a module for its relative imports to resolve correctly. Running inside the
   `melody_generator/` subdirectory will result in `No module named
   melody_generator`.

## Features

### Melody generation
- Supports major, minor and modal scales such as Dorian or Mixolydian
- Offers built-in chord progressions and rhythmic patterns
- Can add harmony or counterpoint lines
- Enforces smooth motion using simple melodic rules
- Style embeddings and a lightweight sequence model tailor note choices

### User interface
- GUI previews the melody before saving and can reload saved preferences
- Web interface provides a WAV preview via FluidSynth

### Output customization
- Dynamic velocity for a more natural sound
- Optional performance humanization with timing and velocity variations
- Optional base octave parameter to constrain the register
- Variations when motifs repeat so phrases remain interesting

### Performance and infrastructure
- Batch export helper uses ``ProcessPoolExecutor`` and Celery for parallel
  generation
- Lookup tables and helpers are memoized with ``functools.lru_cache`` to speed
  up note and scale queries
- Sequence models cached to avoid reloading weights from disk
- Cross-platform setup scripts ship with executable permissions for one-step
  installation

# Requirements
- Python 3.x
- mido (for MIDI generation)
- Flask (for the web interface)
- tkinter (for the GUI)
- PyTorch (optional, enables the pretrained sequence model)
- NumPy (optional, improves tension weighting)

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

Automated helper scripts for macOS, Linux and Windows are documented in
[docs/README_SETUP.md](docs/README_SETUP.md). They install Python,
create a virtual environment and set up the FluidSynth dependency.

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
variable or passing `--settings-file PATH` on the command line before starting
the application. Additional optional variables are
summarized in the [Environment Variables](#environment-variables) section.

## Environment Variables

- `MELODY_SETTINGS_FILE` – Path to the JSON settings file used by the GUI and
  CLI.
- `MELODY_PLAYER` – Optional external MIDI player invoked when previewing files.
- `SOUND_FONT` – Location of a SoundFont (`.sf2`) used for FluidSynth playback.
  When unset the platform defaults are checked in the following order:
  `C:\Windows\System32\drivers\gm.dls` on Windows,
  `/Library/Audio/Sounds/Banks/FluidR3_GM.sf2` on macOS and
  `/usr/share/sounds/sf2/TimGM6mb.sf2` on Linux (from the optional
  `fluid-soundfont-gm` package).
- `FLASK_SECRET` – Secret key for the web interface session. If omitted a
  random key is generated each run.
- `CELERY_BROKER_URL` – URL of the Celery broker used for asynchronous preview
  generation. Defaults to `memory://` so the web interface works without
  additional services.

# Usage

Below are step-by-step examples for the three ways of using the project.

### CLI

Generate a melody entirely from the command line:

```bash
melody-generator \
  --settings-file custom_settings.json \
  --key C \
  --chords C,G,Am,F \
  --bpm 120 \
  --timesig 4/4 \
  --notes 16 \
  --instrument 0 \
  --soundfont /path/to/font.sf2 \
  --output song.mid \
  --no-humanize \
  --harmony --counterpoint --harmony-lines 1 \
  --seed 42
```

This command creates `song.mid` with one harmony line and an additional counterpoint track.
The `--instrument` option selects the General MIDI program number used for the melody.
Pass `--no-humanize` if you want deterministic timing so events align exactly on the beat.
Use `--play` to automatically preview the file once it is written.

Another short example enabling the sequence model and selecting a style:

```bash
melody-generator --settings-file custom_settings.json \
  --key Em --chords Em,G,D,A --bpm 100 --timesig 4/4 \
  --notes 32 --enable-ml --style blues --output jam.mid
```

This command biases note probabilities toward the *blues* style using the
lightweight sequence model.

### GUI

Simply run `melody-generator` with no arguments:

```bash
melody-generator
```

1. Choose a key, BPM, time signature and chord progression.
2. Optionally tick **Use ML Model** and pick a **Style** to bias note choices.
3. Check the **Harmony** or **Counterpoint** boxes to add extra tracks.
4. Leave **Humanize Performance** enabled for natural timing or untick it for strict quantization.
5. Click **Preview Melody** to hear the result without saving.
6. Click **Generate Melody** and select where to save the MIDI file.


### Web Interface

Start the Flask app:

```bash
python -m melody_generator.web_gui
```

1. Open `http://localhost:5000` in your browser.
2. Fill out the form just like the GUI version. Use **Use ML Model** and the
   **Style** drop-down to influence the melody.
3. Keep **Humanize Performance** checked for more realism or uncheck for exact timing.
4. Submit to preview and download the generated file.
5. Set the `FLASK_SECRET` environment variable to a persistent secret. If it
   is not provided a random key is generated on startup and a warning is
   logged.
6. Optionally set `FLASK_DEBUG=1` to enable Flask debug mode during
   development.
7. Set `CELERY_BROKER_URL` to the address of a Celery broker if you want
   preview generation handled asynchronously. If the broker is unreachable the
   server falls back to synchronous generation so your request still succeeds.


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
 - `--harmony-lines N` creates `N` additional harmony parts. Values must be non-negative.
- `--counterpoint` generates a contrapuntal line based on the melody.
- `--base-octave N` sets the starting octave of the melody (0-8,
  default: 4).
- `--list-keys` prints all supported keys and exits.
- `--list-chords` prints all supported chords and exits.
- `--play` previews the resulting MIDI file using FluidSynth when available and
  falls back to the system player otherwise.
- `--soundfont PATH` uses the specified SoundFont when playing the file with
  `--play`.
- `--enable-ml` loads the lightweight sequence model so note weighting is
  informed by training data.
- `--style NAME` selects a predefined style embedding to bias the melody toward
  a genre such as blues or chiptune.
 - `--seed N` sets the random seed for reproducible output.

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
line length and targets Python 3.10. Adjust this file if different rules
are required.

## Continuous Integration

The project relies on GitHub Actions to run tests and lint checks on every
pull request. The workflow defined in `.github/workflows/ci.yml` installs the
package in editable mode along with optional dependencies such as `pyfluidsynth`
and `numpy`. Ruff and pytest are executed to ensure consistent style and
behavior across Python versions. If dependency resolution errors occur in CI,
double-check version pins in `pyproject.toml` and clear any caching steps that
may be present in the workflow configuration.

To build the Docker image locally run:

```bash
docker build -t melody-generator .
```

If this command fails with `command not found`, install Docker or use an
alternative container runtime such as Podman.


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
heuristics is available in [docs/README.md](docs/README.md).
