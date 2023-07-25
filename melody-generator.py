#----------------------------------------
# Author: Austin Boone
# Date: April 18th, 2023
# 
# melody-generator.py
#
# Python script that allows users to create a random melody 
# in a specified key, with a specific BPM (beats per minute) 
# and time signature.
#----------------------------------------

import mido
from mido import Message, MidiFile, MidiTrack
import random
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# Define note names and scales
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SCALE = {
    'C': ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
    'C#': ['C#', 'D#', 'E#', 'F#', 'G#', 'A#', 'B#'],
    'D': ['D', 'E', 'F#', 'G', 'A', 'B', 'C#'],
    'Eb': ['Eb', 'F', 'G', 'Ab', 'Bb', 'C', 'D'],
    'E': ['E', 'F#', 'G#', 'A', 'B', 'C#', 'D#'],
    'F': ['F', 'G', 'A', 'A#', 'C', 'D', 'E'],
    'F#': ['F#', 'G#', 'A#', 'B', 'C#', 'D#', 'E#'],
    'G': ['G', 'A', 'B', 'C', 'D', 'E', 'F#'],
    'Ab': ['Ab', 'Bb', 'C', 'Db', 'Eb', 'F', 'G'],
    'A': ['A', 'B', 'C#', 'D', 'E', 'F#', 'G#'],
    'Bb': ['Bb', 'C', 'D', 'Eb', 'F', 'G', 'A'],
    'B': ['B', 'C#', 'D#', 'E', 'F#', 'G#', 'A#'],
    # Minor keys
    'Cm': ['C', 'D', 'Eb', 'F', 'G', 'Ab', 'Bb'],
    'C#m': ['C#', 'D#', 'E', 'F#', 'G#', 'A', 'B'],
    'Dm': ['D', 'E', 'F', 'G', 'A', 'Bb', 'C'],
    'Ebm': ['Eb', 'F', 'Gb', 'Ab', 'Bb', 'Cb', 'Db'],
    'Em': ['E', 'F#', 'G', 'A', 'B', 'C', 'D'],
    'Fm': ['F', 'G', 'Ab', 'Bb', 'C', 'Db', 'Eb'],
    'F#m': ['F#', 'G#', 'A', 'B', 'C#', 'D', 'E'],
    'Gm': ['G', 'A', 'Bb', 'C', 'D', 'Eb', 'F'],
    'G#m': ['G#', 'A#', 'B', 'C#', 'D#', 'E', 'F#'],
    'Am': ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
    'Bbm': ['Bb', 'C', 'Db', 'Eb', 'F', 'Gb', 'Ab'],
    'Bm': ['B', 'C#', 'D', 'E', 'F#', 'G', 'A']
}

# Define the chords
CHORDS = {
    "C": ["C", "E", "G"],
    "Cm": ["C", "Eb", "G"],
    "C#": ["C#", "E#", "G#"],
    "C#m": ["C#", "E", "G#"],
    "D": ["D", "F#", "A"],
    "Dm": ["D", "F", "A"],
    "Eb": ["Eb", "G", "Bb"],
    "Ebm": ["Eb", "Gb", "Bb"],
    "E": ["E", "G#", "B"],
    "Em": ["E", "G", "B"],
    "F": ["F", "A", "C"],
    "Fm": ["F", "Ab", "C"],
    "F#": ["F#", "A#", "C#"],
    "F#m": ["F#", "A", "C#"],
    "G": ["G", "B", "D"],
    "Gm": ["G", "Bb", "D"],
    "G#": ["G#", "B#", "D#"],
    "G#m": ["G#", "B", "D#"],
    "A": ["A", "C#", "E"],
    "Am": ["A", "C", "E"],
    "Bb": ["Bb", "D", "F"],
    "Bbm": ["Bb", "Db", "F"],
    "B": ["B", "D#", "F#"],
    "Bm": ["B", "D", "F#"]
}

# Define some common rhythmic patterns (in terms of fractions of a whole note)
PATTERNS = [
    [0.25, 0.25, 0.5],  # quarter, quarter, half
    [0.25, 0.75],  # quarter, dotted half
    [0.5, 0.5],  # half, half
    [0.375, 0.375, 0.25]  # dotted quarter, dotted quarter, quarter
]

def note_to_midi(note):
    """
    Convert a note name to a MIDI note number.

    Args:
        note (str): The note name (e.g., 'C#4').

    Returns:
        int: The MIDI note number.
    """
    # Extract octave number from note name and adjust it for MIDI format
    octave = int(note[-1]) + 1
    
    # Find the index of the note in the notes list
    note_idx = NOTES.index(note[:-1])
    
    # Calculate and return the MIDI note number
    return note_idx + (octave * 12)

def get_interval(note1, note2):
    """Get the interval between two notes in semitones."""
    return abs(note_to_midi(note1) - note_to_midi(note2))

def get_chord_notes(chord):
    """
    Get the notes in a chord.

    Args:
        chord (str): The chord name (e.g., 'C', 'F#m').

    Returns:
        list: The notes in the chord.
    """
    return CHORDS[chord]

def generate_motif(length, key):
    """
    Generate a motif of a given length in a given key.

    Args:
        length (int): The length of the motif.
        key (str): The musical key.

    Returns:
        list: The generated motif as a list of note names.
    """
    notes_in_key = SCALE[key]
    motif = [random.choice(notes_in_key) + str(random.randint(4, 6)) for _ in range(length)]
    return motif

def generate_melody(key, num_notes, chord_progression, motif_length=4):
    """
    Generate a random melody in the given key, using a specified chord progression and a repeating motif.

    This code works by initially creating a motif, then extending that motif into a full melody. 
    The melody is built note by note, always trying to choose the next note that is in the current chord 
    and that has the smallest possible interval to the previous note. 
    This is done to make the melody sound smoother and more natural.

    Args:
        key (str): The musical key.
        num_notes (int): The number of notes in the melody.
        chord_progression (list): The chord progression.
        motif_length (int): The length of the repeating motif.

    Returns:
        list: The generated melody as a list of note names.
    """
   # Fetch the scale for the key the melody is in
notes_in_key = SCALE[key]

# Generate a musical motif (a short, recurring musical idea) within the key
motif = generate_motif(motif_length, key)

# The motif is the starting point of our melody
melody = motif.copy()

# Continue generating the rest of the melody beyond the initial motif
for i in range(motif_length, num_notes):
    # We choose the chord based on our chord progression. The chord is used to give a sense of harmony.
    # We cycle through the chord progression by using the modulo (%) operator.
    chord = chord_progression[i % len(chord_progression)]

    # Fetch the notes that make up this chord
    chord_notes = get_chord_notes(chord)

    # The previous note is used to ensure the melody has smooth transitions
    prev_note = melody[-1]

    # Initialize the next note to be chosen and the minimum interval
    next_note = None
    min_interval = len(NOTES)

    # We iterate through each note in our scale
    for note in notes_in_key:
        # We consider three octaves to give the melody some range
        for octave in range(4, 7):
            # Create a note in the current octave
            note_with_octave = note + str(octave)

            # Calculate the interval between this note and the previous note
            interval = get_interval(prev_note, note_with_octave)

            # If this interval is smaller than our current smallest interval and the note is in the current chord,
            # we choose this note as our next note
            if interval < min_interval and note in chord_notes:
                next_note = note_with_octave
                min_interval = interval

    # Add the chosen note to the melody
    melody.append(next_note)

# Return the complete melody
return melody


def create_midi_file(melody, bpm, time_signature, output_file):
    """
    Create a MIDI file with the given melody, BPM, and time signature.

    Args:
        melody (list): The melody as a list of note names.
        bpm (int): The BPM (beats per minute).
        time_signature (tuple): The time signature as a tuple (numerator, denominator).
        output_file (str): The path to the output MIDI file.
    """
    # Set ticks per beat (resolution) for the MIDI file
    ticks_per_beat = 480
    
    # Create a new MIDI file with the specified ticks_per_beat
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    
    # Create a new MIDI track and add it to the MIDI file
    track = MidiTrack()
    mid.tracks.append(track)

    # Set the BPM (tempo) for the MIDI file
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    
    # Set the time signature for the MIDI file
    track.append(mido.MetaMessage('time_signature', numerator=time_signature[0], denominator=time_signature[1]))

    # Define note lengths (quarter, half, and whole notes)
    note_lengths = [ticks_per_beat // 2, ticks_per_beat, ticks_per_beat * 2]

    # Add the notes from the melody to the MIDI track
    for note in melody:
        # Choose a random note length
        note_length = random.choice(note_lengths)
        
        # Create note_on and note_off events for the current note
        note_on = Message('note_on', note=note_to_midi(note), velocity=64, time=0)
        note_off = Message('note_off', note=note_to_midi(note), velocity=64, time=note_length)
        
        # Append the note_on and note_off events to the MIDI track
        track.append(note_on)
        track.append(note_off)

    # Save the generated MIDI file
    mid.save(output_file)

def main():
    # Function called when the "Generate Melody" button is clicked
    def generate_button_click():
        # Retrieve user input from the GUI elements
        key = key_entry.get()
        chord_progression = chord_progression_entry.get().split(',')
        try:
            bpm = int(bpm_entry.get())
            time_signature = (int(time_signature_numerator_entry.get()), int(time_signature_denominator_entry.get()))
            num_notes = int(num_notes_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "BPM, Time Signature and Number of notes should be integers.")
            return

        if key not in SCALE.keys():
            messagebox.showerror("Input Error", "Invalid key.")
            return

        for chord in chord_progression:
            if chord not in CHORDS.keys():
                messagebox.showerror("Input Error", f"Invalid chord: {chord}")
                return

        # Open a file dialog for the user to choose the output MIDI file location
        output_file = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if output_file:
            # Generate the melody and create the MIDI file
            melody = generate_melody(key, num_notes, chord_progression)
            create_midi_file(melody, bpm, time_signature, output_file)

    # Create the main tkinter window
    root = tk.Tk()
    root.title("Melody Generator")

    # Create and position the "Key" label and entry field
    key_label = tk.Label(root, text="Key:")
    key_label.grid(row=0, column=0)
    key_entry = tk.Entry(root)
    key_entry.grid(row=0, column=1)

    # Create and position the "Chord Progression" label and entry field
    chord_progression_label = tk.Label(root, text="Chord Progression:")
    chord_progression_label.grid(row=1, column=0)
    chord_progression_entry = tk.Entry(root)
    chord_progression_entry.grid(row=1, column=1)

    # Create and position the "BPM" label and entry field
    bpm_label = tk.Label(root, text="BPM:")
    bpm_label.grid(row=2, column=0)
    bpm_entry = tk.Entry(root)
    bpm_entry.grid(row=2, column=1)

    # Create and position the "Time signature" label and entry fields
    time_signature_label = tk.Label(root, text="Time signature:")
    time_signature_label.grid(row=3, column=0)
    time_signature_numerator_entry = tk.Entry(root)
    time_signature_numerator_entry.grid(row=3, column=1)
    time_signature_denominator_entry = tk.Entry(root)
    time_signature_denominator_entry.grid(row=3, column=2)

    # Create and position the "Number of notes" label and entry field
    num_notes_label = tk.Label(root, text="Number of notes:")
    num_notes_label.grid(row=4, column=0)
    num_notes_entry = tk.Entry(root)
    num_notes_entry.grid(row=4, column=1)

    # Create and position the "Generate Melody" button
    generate_button = tk.Button(root, text="Generate Melody", command=generate_button_click)
    generate_button.grid(row=5, column=0, columnspan=2)

    # Start the tkinter main loop to display the GUI
    root.mainloop()

if __name__ == '__main__':
    main()
