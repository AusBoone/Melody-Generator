# Melody-Generator
Python script that allows users to create a random melody in a specified key, with a specific BPM (beats per minute) and time signature. The generated melody can be saved as a MIDI file.

# Requirements
- Python 3.x
- mido
- tkinter

# Installation
1) Install the required packages:
**pip install mido**
2) Download the melody-generator.py script.

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
