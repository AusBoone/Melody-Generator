# FluidSynth Dependency

FluidSynth provides the real-time synthesizer used by Melody-Generator to preview
and render melodies. The Python package `pyFluidSynth` is installed
automatically, but the underlying system library must also be present.

## Installation

### Linux
Install the library and development headers:
```bash
sudo apt-get install fluidsynth libfluidsynth-dev
```

### macOS
Use Homebrew:
```bash
brew install fluid-synth
```

### Windows
Install via [winget](https://learn.microsoft.com/windows/package-manager/winget/):
```powershell
winget install FluidSynth
```

After installation the `fluidsynth --version` command should print the version
number. If the command is not found make sure your PATH includes the directory
containing the executable.

## Usage Notes

- The optional environment variable `SOUND_FONT` points to a General MIDI
  SoundFont used by FluidSynth. See [README_SOUND_FONTS.md](README_SOUND_FONTS.md)
  for recommendations.
- Without FluidSynth installed the GUI preview button and web interface will
  log errors when trying to play or render audio, but MIDI files can still be
  generated normally.

