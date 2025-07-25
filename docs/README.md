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

Each document is self-contained so you can jump directly to the topic that
interests you.

### Web Interface

Launch the Flask application with `python -m melody_generator.web_gui` and open
`http://localhost:5000` in your browser. The form mirrors the desktop GUI so you
can choose a key, tempo and chord progression. Selecting **Random Rhythm** now
generates the pattern using the full note count. Internally the server calls
`generate_random_rhythm_pattern(notes)` so the rhythm list length matches the
melody.
