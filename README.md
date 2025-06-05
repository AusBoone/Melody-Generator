# Melody-Generator
Python script that allows users to create a random melody in a specified key, with a specific BPM (beats per minute) and time signature. The generated melody can be saved as a MIDI file.

# Requirements
- Python 3.x
- mido
- tkinter
- Flask (optional, for the web interface)

# Installation
1) Install the required packages:
You can install them all at once with:
```bash
pip install -r requirements.txt
```
or individually:
```bash
pip install mido tkinter Flask
```
2) Download the **melody-generator.py** script.

# Settings
User preferences such as BPM and key are stored in a JSON file located at
`~/.melody_generator_settings.json`. The GUI loads this file on startup and you
can choose to save your current selections after generating a melody.

# Usage
Run the script:
**python melody-generator.py**
- This will open the Melody Generator GUI, where you can select the key, adjust BPM and note count with sliders, choose a time signature from a drop-down, and optionally add a harmony line.
- Use the **Randomize Chords** and **Randomize Rhythm** buttons if you want the application to choose a chord progression and rhythmic pattern for you.
- After entering this information, click the "Generate Melody" button to create your random melody.
- You will be prompted to choose a location to save the generated MIDI file.

For a web-based interface, run:
```bash
python web_gui.py
```
Then open `http://localhost:5000` in your browser to generate melodies and download the MIDI file.

## Docker Usage
Build the image and run the web interface:
```bash
docker build -t melody-generator .
docker run -p 5000:5000 melody-generator
```
Then visit `http://localhost:5000` in your browser.

# Parameters
- **Key**: Enter the key for the melody (e.g., C, C#, Dm, etc.). Both major and minor keys are supported.
- **BPM**: Adjust the tempo using the slider (e.g., 120 BPM).
- **Time Signature**: Choose the time signature from the drop-down (e.g., 4/4, 3/4).
- **Number of notes**: Set how many notes to generate with the slider.
- **Harmony**: Tick this option to add a simple harmony line.

## CLI Flags
When running from the command line you can supply optional flags:
- `--random-chords N` generates a progression of `N` random chords and ignores `--chords`.
- `--random-rhythm` creates a random rhythmic pattern for the melody.

# New Features

- Automatic chord progressions based on common pop patterns.
- Expanded rhythmic patterns including eighth- and sixteenth-note figures.
- Melodic rules such as leap compensation to avoid jarring jumps.
- Variations when motifs repeat so phrases remain interesting.
- Additional modes like Dorian, Mixolydian and pentatonic scales.
- Dynamic velocity in the MIDI output for a more natural sound.
- GUI button to reload saved preferences at any time.
- Web interface now previews the generated MIDI using an inline player.

# Future Work

- Harmony and counterpoint options for multi-line melodies.
