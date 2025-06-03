# Melody-Generator
Python script that allows users to create a random melody in a specified key, with a specific BPM (beats per minute) and time signature. The generated melody can be saved as a MIDI file.

# Requirements
- Python 3.x
- mido
- tkinter

# Installation
1) Install the required packages:
You can install them all at once with:
```bash
pip install -r requirements.txt
```
or individually:
```bash
pip install mido tkinter
```
2) Download the **melody-generator.py** script.

# Usage
Run the script:
**python melody-generator.py**
- This will open the Melody Generator GUI, where you can enter the desired key, BPM, time signature, and number of notes for your melody. 
- After entering this information, click the "Generate Melody" button to create your random melody. 
- You will be prompted to choose a location to save the generated MIDI file.

# Parameters
- **Key**: Enter the key for the melody (e.g., C, C#, Dm, etc.). Both major and minor keys are supported.
- **BPM**: Enter the beats per minute for the melody (e.g., 120).
- **Time Signature**: Enter the time signature for the melody in the format "numerator/denominator" (e.g., 4/4, 3/4, etc.).
- **Number of notes**: Enter the desired number of notes in the generated melody.

# Future Work & Improvements 

- Incorporate Chord Progressions: The script accepts a chord progression as input but doesn’t automatically generate one. To improve the script, consider adding functionality that generates common chord progressions based on the selected key. This could be done by specifying a list of popular progressions (like I-IV-V-I) and choosing one randomly or using a specific pattern.
- Use Note Durations: Right now, the script uses random note lengths, choosing from quarter, half, and whole notes. This could be improved by using more rhythmic diversity, such as eighth notes or sixteenth notes. It might also be beneficial to generate rhythmic motifs, much like the pitch motifs already being generated, to give the melody a more consistent rhythmic feel.
- Implement Melodic Rules: The script could benefit from implementing some rules from melodic theory to make the melodies sound more pleasing. For example, leaps (intervals of more than a step) could be followed by a step in the opposite direction, a concept known as "leap compensation." Additionally, the script could limit the size of leaps or ensure that the melody doesn't leap too many times in succession.
- Introduce Variations: The script could introduce slight variations each time the motif repeats. This could involve changing a note's pitch or duration, adding or removing notes, or inverting or reversing the motif. These variations can prevent the melody from sounding too repetitive.
- Harmony and Counterpoint: Currently, the script generates a single melody line. Incorporating harmony or counterpoint could add depth and complexity to the output. A simple harmony could duplicate the melody at a fixed interval, while a more complex counterpoint could generate a second melody that complements the first.
- User-Friendly GUI: The current GUI is quite basic. It could be improved by providing dropdown menus for the key and time signature, sliders for BPM and number of notes, and a checkbox for selecting whether to generate a harmony.
- Include More Scales and Modes: The current version includes only major and minor scales. By including other scales like Dorian, Mixolydian, Pentatonic, and others, the tool could generate a wider variety of melodies.
- Dynamic Velocity: The script currently uses a fixed velocity (volume) for all notes. Implementing dynamic velocity could make the melody more expressive. The velocity could vary randomly, or the script could implement a larger structure, such as a crescendo or decrescendo.
