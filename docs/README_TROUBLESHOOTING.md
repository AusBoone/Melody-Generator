# Troubleshooting & FAQ

This guide documents common issues encountered when running Melody-Generator and
provides actionable steps to resolve them. Follow the sections in order; each
one builds on assumptions verified earlier in the Quick Start checklist.

## Installation Problems

### `pip install .` fails
- **Symptom**: Installation aborts with compiler errors.
- **Resolution**: Ensure you have a recent version of `pip` (`python -m pip
  install --upgrade pip`). The project itself ships pure Python code, but
  optional dependencies such as PyTorch may require build tools. Install
  platform SDKs where necessary (Xcode Command Line Tools on macOS,
  `build-essential` on Debian/Ubuntu).

### Entry point not found
- **Symptom**: `melody-generator` command is not recognized after installation.
- **Resolution**: Verify that the Python environment's `bin` (Unix) or `Scripts`
  (Windows) directory is on your `PATH`. Reactivate the virtual environment or
  reinstall using `pip install -e .` to regenerate the console script.

## Audio Playback Issues

### No sound when previewing
- **Symptom**: GUI/Web previews run but produce silence.
- **Resolution**:
  1. Install FluidSynth (`sudo apt install fluidsynth`, `brew install fluidsynth`
     or download the Windows binary).
  2. Download a General MIDI `.sf2` soundfont (see
     [README_SOUND_FONTS.md](README_SOUND_FONTS.md)).
  3. Set the `SOUND_FONT` environment variable to the `.sf2` file path or pass
     `--soundfont` when invoking the CLI.
  4. Re-run the preview. If audio is still missing, start the GUI/Web app from a
     terminal and inspect the logs for a warning about FluidSynth.

### FluidSynth missing libraries
- **Symptom**: Errors mention `libfluidsynth` or similar shared libraries.
- **Resolution**: On Linux install the matching `libfluidsynth` package (for
  example `sudo apt install libfluidsynth3`). On macOS use Homebrew to install
  dependencies automatically. On Windows ensure the DLLs shipped with the
  FluidSynth distribution sit next to the executable or are on the `PATH`.

## Web Application Problems

### Flask refuses to start without `FLASK_SECRET`
- **Symptom**: Running the server exits immediately complaining about a missing
  secret key.
- **Resolution**: Set `FLASK_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")`
  in your shell before launching Flask. Persist the value in deployment
  environments so sessions remain valid between restarts.

### Preview requests hang
- **Symptom**: Submitting the form never returns or times out.
- **Resolution**: Confirm a Celery broker is reachable if you configured one.
  If asynchronous previews are unnecessary, unset `CELERY_BROKER_URL` so Flask
  falls back to synchronous processing. Check worker logs for exceptions when
  the broker is enabled.

## Machine Learning Features

### PyTorch import errors
- **Symptom**: Enabling **Use ML Model** raises `ModuleNotFoundError: No module named 'torch'`.
- **Resolution**: Install PyTorch following the instructions at
  <https://pytorch.org/get-started/locally/>. CPU builds work fine for inference;
  GPU acceleration is optional.

### Style embeddings not found
- **Symptom**: CLI reports `Unknown style` or the GUI list is empty.
- **Resolution**: Ensure `melody_generator/style/example_styles.json` is present
  and readable. For custom embeddings, confirm the JSON file and associated
  weight files reside in `melody_generator/style/models/` and that the
  `STYLE_EMBEDDINGS_PATH` environment variable (if set) points to the directory.

## Logging & Diagnostics

- Launch the CLI/GUI/Web app from a terminal so log messages appear in real
  time. Increase verbosity by setting `MELODY_DEBUG=1` to print extra details
  about scale selection and MIDI export.
- Use `pytest -k failing_test_name -vv` to rerun a single failing test with
  verbose output when debugging regressions.
- If you suspect a platform-specific bug, include the OS version, Python
  version (`python --version`) and FluidSynth version in any bug report.

Refer back to the [Development Guide](README_DEVELOPMENT.md) for best practices
when modifying the codebase or extending the test suite.
