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
from tkinter import filedialog

def note_to_midi(note):
    """
    Convert a note name to a MIDI note number.
    """
    # List of note names
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Extract octave number from note name and adjust it for MIDI format
    octave = int(note[2]) + 2
    
    # Find the index of the note in the notes list
    note_idx = notes.index(note[:2])
    
    # Calculate and return the MIDI note number
    return note_idx + (octave * 12)

def generate_melody(key, num_notes):
    """
    Generate a random melody in the given key.
    """
    # Dictonary defining scales for the available keys
    scale = {
        # Major keys
        'C': ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
        'C#': ['C#', 'D#', 'E#', 'F#', 'G#', 'A#', 'B#'],
        'D': ['D', 'E', 'F#', 'G', 'A', 'B', 'C#'],
        'Eb': ['Eb', 'F', 'G', 'Ab', 'Bb', 'C', 'D'],
        'E': ['E', 'F#', 'G#', 'A', 'B', 'C#', 'D#'],
        'F': ['F', 'G', 'A', 'Bb', 'C', 'D', 'E'],
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

    # Get the notes in the specified key
    notes_in_key = scale[key]
    
    # Generate the random melody with num_notes length
    melody = [random.choice(notes_in_key) + str(random.randint(4, 6)) for _ in range(num_notes)]
    
    return melody

def create_midi_file(melody, bpm, time_signature, output_file):
    """
    Create a MIDI file with the given melody, BPM, and time signature.
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
        bpm = int(bpm_entry.get())
        time_signature = tuple(map(int, time_signature_entry.get().split()))
        num_notes = int(num_notes_entry.get())
        
        # Open a file dialog for the user to choose the output MIDI file location
        output_file = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if output_file:
            # Generate the melody and create the MIDI file
            melody = generate_melody(key, num_notes)
            create_midi_file(melody, bpm, time_signature, output_file)

    # Create the main tkinter window
    root = tk.Tk()
    root.title("Melody Generator")

    # Create and position the "Key" label and entry field
    key_label = tk.Label(root, text="Key:")
    key_label.grid(row=0, column=0)
    key_entry = tk.Entry(root)
    key_entry.grid(row=0, column=1)

    # Create and position the "BPM" label and entry field
    bpm_label = tk.Label(root, text="BPM:")
    bpm_label.grid(row=1, column=0)
    bpm_entry = tk.Entry(root)
    bpm_entry.grid(row=1, column=1)

    # Create and position the "Time signature" label and entry field
    time_signature_label = tk.Label(root, text="Time signature:")
    time_signature_label.grid(row=2, column=0)
    time_signature_entry = tk.Entry(root)
    time_signature_entry.grid(row=2, column=1)

    # Create and position the "Number of notes" label and entry field
    num_notes_label = tk.Label(root, text="Number of notes:")
    num_notes_label.grid(row=3, column=0)
    num_notes_entry = tk.Entry(root)
    num_notes_entry.grid(row=3, column=1)

    # Create and position the "Generate Melody" button
    generate_button = tk.Button(root, text="Generate Melody", command=generate_button_click)
    generate_button.grid(row=4, column=0, columnspan=2)

    # Start the tkinter main loop to display the GUI
    root.mainloop()

if __name__ == '__main__':
    main()
