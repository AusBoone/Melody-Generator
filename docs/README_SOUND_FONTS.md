# SoundFont Resources

FluidSynth and the built-in MIDI player rely on a General MIDI
soundfont (`.sf2` file) to render audio. Below are a few freely
available options along with basic installation tips.

- **FluidR3 GM** – Packaged as `fluid-soundfont-gm` on many Linux
  distributions. Install via your package manager when possible.
- **GeneralUser GS** – A high quality GM bank maintained by S. Christian
  Collins. Download from <https://schristiancollins.com/generaluser.php>
  and place the `.sf2` file somewhere convenient.
- **Musyng Kite** – Large but well regarded. Available from
  <https://musical-artifacts.com>.

Once downloaded, set the `SOUND_FONT` environment variable to the path of
your chosen file. The CLI and GUI will use it automatically when playing
MIDI files through FluidSynth. If `SOUND_FONT` is not set the code
attempts to use `/usr/share/sounds/sf2/TimGM6mb.sf2` which is installed
with the optional `fluid-soundfont-gm` package on many Linux
distributions.
For instructions on installing the FluidSynth engine see
[README_FLUIDSYNTH.md](README_FLUIDSYNTH.md).
