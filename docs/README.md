# Melody-Generator Documentation

This directory groups the extended guides for the project. Start here if you need
additional background on how the system works or how to configure audio playback.

- [Algorithm Overview](README_ALGORITHM.md) – In depth look at the heuristics used
  when constructing melodies.
- [Setup Guide](README_SETUP.md) – Quick scripts for installing dependencies on
  macOS, Linux and Windows.
- [FluidSynth Dependency](README_FLUIDSYNTH.md) – Installing the audio engine
  used for playback and preview.
- [SoundFont Resources](README_SOUND_FONTS.md) – Lists free General MIDI banks and
  explains how to configure FluidSynth for playback.
- [Machine Learning Concepts](README_ML_CONCEPTS.md) – Overview of the sequence
  model, style embeddings and tension weighting used in the generator.
- [Musician's Overview](README_MUSICAL_OVERVIEW.md) – Introduction to the
  project for classical performers and composers.
- [Training Larger Models](README_TRAINING.md) – Guide for fitting
  Transformer/ VAE models on genre-specific MIDI datasets.
- [Development Guide](README_DEVELOPMENT.md) – Coding standards, testing
  strategy and release process for contributors.
- [Troubleshooting & FAQ](README_TROUBLESHOOTING.md) – Practical fixes for
  installation, audio and deployment issues.

Each document is self-contained so you can jump directly to the topic that
interests you.

### Optional Dependencies & Deployment

Some features rely on additional tools. Installing them enables audio previews
and background processing but they are not strictly required.

- **FluidSynth & SoundFont** – Render audio previews by installing FluidSynth
  (e.g., ``sudo apt-get install fluidsynth`` or ``brew install fluidsynth``) and
  providing a General MIDI ``.sf2`` soundfont. Point the ``SOUNDFONT``
  environment variable at the file or pass ``--soundfont`` on the command line
  so previews use the desired instrument bank.
- **Celery Broker** – Asynchronous preview generation uses Celery. Install a
  broker such as Redis and start a worker:

  ```bash
  pip install celery redis
  export CELERY_BROKER_URL=redis://localhost:6379/0
  celery -A melody_generator.web_gui.celery_app worker --loglevel=info
  ```

  If the broker is unreachable the application falls back to synchronous
  preview generation.
- **Machine Learning Libraries** – Style embeddings and tension weighting
  require PyTorch and NumPy:

  ```bash
  pip install torch numpy
  ```

  These libraries are optional when using only the rule-based generator.

### Web Interface

Launch the Flask application with `python -m melody_generator.web_gui` and open
`http://localhost:5000` in your browser. The form mirrors the desktop GUI so you
can choose a key, tempo and chord progression. Selecting **Random Rhythm** now
generates the pattern using the full note count. Internally the server calls
`generate_random_rhythm_pattern(notes)` so the rhythm list length matches the
melody.
