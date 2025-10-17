# Melody-Generator
Melody-Generator is a research-oriented project that provides a simple yet versatile engine for
generating melodies in any key, tempo and meter. The output can be rendered to a standard MIDI
file for use in digital audio workstations. For a formal exposition of the algorithm see
[docs/README.md](docs/README.md).

## Documentation

The [docs/README.md](docs/README.md) index links to deep dives on the
generation algorithm, setup automation, audio dependencies and optional
machine-learning features. It now also includes focused guides for development
workflow and troubleshooting the most common runtime issues so you can move
from installation to experimentation without guesswork.

If you are unsure where to begin, skim the [Quick Start](#quick-start)
checklist below and then consult the dedicated guides when you need additional
background information.

## Quick Start

The following flow walks through the minimum steps required to generate your
first melody and verify that audio playback works end-to-end:

1. **Install system dependencies** – Ensure Python 3.10+ is available and, if
   you want audio previews, install FluidSynth together with at least one
   General MIDI soundfont (see
   [docs/README_FLUIDSYNTH.md](docs/README_FLUIDSYNTH.md)).
2. **Create and activate a virtual environment** – Avoid polluting your global
   interpreter by running `python -m venv .venv` followed by
   `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows).
3. **Install the package** – Run `pip install .` from the repository root. Use
   `pip install -e .` instead if you plan to edit the codebase.
4. **Verify the CLI** – Execute `melody-generator --list-keys` to confirm the
   command-line entry point is on your `PATH` and the Python package imports
   correctly.
5. **Launch the GUI** – Run `melody-generator` with no arguments, change a few
   parameters and click **Preview Melody**. If audio fails to play back, refer
   to [docs/README_TROUBLESHOOTING.md](docs/README_TROUBLESHOOTING.md) for
   platform-specific fixes.
6. **Explore advanced features** – Enable **Use ML Model** and select a style
   such as `blues` or `retro_chip` to hear how the optional PyTorch model
   changes the generated phrases.

This process ensures the core components (Python environment, optional audio
tooling and entry points) work before you dive deeper into customization or
deployment.

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
- Playback page now surfaces a session summary detailing tempo, harmony options
  and ML toggles so you can quickly confirm your selections before exporting.

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

## Architecture Overview

Melody-Generator is deliberately modular so you can adopt only the pieces that
fit your workflow:

- **Core engine (`melody_generator/generator.py`)** – Implements the
  rule-based heuristics for melody, harmony and counterpoint generation. The
  module exposes helpers for selecting scales, weighting notes and exporting
  MIDI files.
- **Style layer (`melody_generator/style`)** – Provides optional PyTorch-based
  sequence models and embedding loaders that bias note selection toward a
  genre. If PyTorch or NumPy are unavailable the engine falls back to the
  deterministic heuristics without failing.
- **User interfaces** –
  - **CLI (`melody_generator/__main__.py`)** drives the generator through a
    comprehensive set of arguments intended for automation.
  - **Desktop GUI (`melody_generator/gui.py`)** wraps the engine in a Tkinter
    application with live preview controls.
  - **Web interface (`melody_generator/web_gui`)** exposes the same controls
    over HTTP via Flask and optionally delegates audio rendering to Celery
    workers.
- **Supporting utilities** – Shared helpers handle persistence of user
  settings, MIDI playback fallbacks and dataset loading for training custom
  models.

Understanding this separation makes it easier to extend the system. For
instance, you can build a custom front-end by importing the generator module or
swap in a new ML model by updating the style layer while leaving the CLI/GUI
unchanged.

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
- `FLASK_SECRET` – Secret key for the web interface session. **Must** be set to a
  long, random value in production; the server now refuses to start when this
  variable is missing. A random key is generated only during development to
  keep sessions isolated between restarts.
- `CELERY_BROKER_URL` – URL of the Celery broker used for asynchronous preview
  generation. In production this must reference a real broker such as Redis or
  RabbitMQ. The application exits with an error if the variable is unset. During
  development it defaults to `memory://` so the web interface works without
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
Add `--plagal-cadence` when you want the generator to reharmonise the final
measure as a IV–I "Amen" cadence with a matching soprano descent.

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
4. Toggle **Plagal Cadence** if you want the last bar to resolve with a IV–I ending.
5. Leave **Humanize Performance** enabled for natural timing or untick it for strict quantization.
6. Click **Preview Melody** to hear the result without saving.
7. Click **Generate Melody** and select where to save the MIDI file.


### Web Interface

Run the application with Flask's built-in server during development:

```bash
flask --app melody_generator.web_gui:create_app run
```

For production deployments use a WSGI server such as Gunicorn:

```bash
gunicorn 'melody_generator.web_gui:create_app()'
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


## Verifying Your Installation

After completing the Quick Start steps you can run the following commands to
ensure everything is wired up correctly:

- `pytest` – Executes nearly 300 unit tests that cover the generator, CLI/GUI
  integrations and web endpoints. A passing run confirms the package and its
  mocked dependencies are importable.
- `ruff check .` – Lints the repository using the project's configuration in
  `ruff.toml`. Running the linter ensures your local editor and CI environment
  agree on formatting and style.
- `python -m melody_generator.web_gui` – Starts the Flask development server.
  Open `http://localhost:5000` and submit a form to confirm Celery fallbacks
  and audio previews behave as expected.

If any of these commands fail, consult the
[Troubleshooting guide](docs/README_TROUBLESHOOTING.md) for diagnostic steps.


## Docker Usage
Melody-Generator ships with a fully configured `Dockerfile` that installs the
Python dependencies together with FluidSynth and a General MIDI soundfont so the
web preview works out of the box. This section walks through building and
running the container as well as the most common configuration knobs.

### Prerequisites
- Docker Engine 20.10+ (or a compatible runtime such as Podman).
- At least 1 GB of free disk space for the base Python image and installed
  dependencies.

### Build the image
Build the image from the project root:

```bash
docker build -t melody-generator .
```

The build installs the packages listed in `requirements.txt` and configures the
container entry point to launch the Flask web interface
(`python -m melody_generator.web_gui`).

### Run the web interface
Start the container and expose the Flask development server on port 5000:

```bash
docker run --rm -p 5000:5000 melody-generator
```

This command binds the container's port 5000 to the same port on the host so
you can open `http://localhost:5000` and use the web UI without installing
Python locally.

### Configure environment variables
The web interface reads a handful of environment variables for production
deployments:

- `FLASK_SECRET` – Session signing key. Required when running with Flask debug
  mode disabled. A random key is generated automatically for development runs,
  but sessions will reset between container restarts.
- `CELERY_BROKER_URL` – Connection string for the optional Celery worker used to
  render previews asynchronously. Required in production mode. Omit the
  variable to use the in-memory broker for local experiments.
- `MAX_UPLOAD_MB` – Maximum request size (defaults to 5 MB). Increase this if
  you expect larger form submissions.
- `RATE_LIMIT_PER_MINUTE` – Optional integer throttle applied per client IP.

You can pass these variables to `docker run` with repeated `-e` flags, for
example:

```bash
docker run --rm -p 5000:5000 \
    -e FLASK_SECRET="change-me" \
    -e CELERY_BROKER_URL="redis://redis:6379/0" \
    melody-generator
```

Set `FLASK_DEBUG=1` or `FLASK_ENV=development` if you want Flask's live reload
inside the container.

### Persist generated files
Any MIDI files exported through the container live inside `/app`. Mount a host
directory if you want to keep them after the container exits:

```bash
docker run --rm -p 5000:5000 \
    -v "$(pwd)/exports:/app/exports" \
    melody-generator
```

The web interface saves downloads to a temporary directory by default, but the
volume mount ensures anything you explicitly export within `/app/exports`
survives container restarts.

### Command-line usage inside the container
The image also bundles the CLI entry point. Use `docker run` with `--entrypoint`
to access it without running the web server:

```bash
docker run --rm -it --entrypoint python melody-generator -m melody_generator.cli --help
```

Refer to [docs/README_DOCKER.md](docs/README_DOCKER.md) for an end-to-end
workflow covering multi-container setups and troubleshooting.

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

For a deeper dive into module responsibilities, testing strategy and release
management, read [docs/README_DEVELOPMENT.md](docs/README_DEVELOPMENT.md).

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
