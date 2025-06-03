#!/usr/bin/env python3
"""
Melody Generator: 
A Python script that creates a random melody in a specified key with a given BPM and time signature.
Features include:
- Integrated rhythmic patterns for note durations.
- Enhanced melody generation with controlled randomness.
- Robust fallback mechanisms for note selection.
- Both GUI (tkinter) and CLI interfaces.
- Detailed logging and improved documentation.
Author: Austin Boone
Modified: February 15, 2025
"""

import mido
from mido import Message, MidiFile, MidiTrack
import random
import sys
import logging
import argparse
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from typing import List, Tuple

# Configure logging for debug and info messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define note names and scales
# NOTE_TO_SEMITONE maps both sharp and flat spellings to the correct
# semitone offset within an octave so that functions like ``note_to_midi``
# can handle enharmonic notes (e.g. ``Db`` and ``C#``).
NOTE_TO_SEMITONE = {
    'C': 0,
    'B#': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'Fb': 4,
    'E#': 5,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11,
    'Cb': 11,
}

# Keep a basic list of note names (using sharps) for any other logic that
# relies on it.
NOTES: List[str] = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
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

# Define chords with their constituent notes
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

# Define rhythmic patterns as fractions of a whole note
PATTERNS: List[List[float]] = [
    [0.25, 0.25, 0.5],    # quarter, quarter, half
    [0.25, 0.75],         # quarter, dotted half
    [0.5, 0.5],           # half, half
    [0.375, 0.375, 0.25]   # dotted quarter, dotted quarter, quarter
]

def note_to_midi(note: str) -> int:
    """
    Convert a note name (with octave) to a MIDI note number.
    Example: 'C#4' -> 61 (with C4 as MIDI note 60).

    Args:
        note (str): Note name (e.g., 'C#4').

    Returns:
        int: Corresponding MIDI note number.
    """
    try:
        octave = int(note[-1]) + 1
    except ValueError:
        logging.error(f"Invalid note format: {note}")
        raise

    note_name = note[:-1]
    try:
        note_idx = NOTE_TO_SEMITONE[note_name]
    except KeyError:
        logging.error(f"Note {note_name} not recognized.")
        raise
    return note_idx + (octave * 12)

def get_interval(note1: str, note2: str) -> int:
    """
    Get the interval between two notes in semitones.

    Args:
        note1 (str): First note (e.g., 'C4').
        note2 (str): Second note (e.g., 'E4').

    Returns:
        int: Interval in semitones.
    """
    return abs(note_to_midi(note1) - note_to_midi(note2))

def get_chord_notes(chord: str) -> List[str]:
    """
    Retrieve the notes that make up the given chord.

    Args:
        chord (str): Chord name (e.g., 'C', 'F#m').

    Returns:
        List[str]: List of note names in the chord.
    """
    return CHORDS[chord]

def generate_motif(length: int, key: str) -> List[str]:
    """
    Generate a motif (short, recurring musical idea) in the specified key.

    Args:
        length (int): Number of notes in the motif.
        key (str): Musical key.

    Returns:
        List[str]: List of note names forming the motif.
    """
    notes_in_key = SCALE[key]
    return [random.choice(notes_in_key) + str(random.randint(4, 6)) for _ in range(length)]

def generate_melody(key: str, num_notes: int, chord_progression: List[str], motif_length: int = 4) -> List[str]:
    """
    Generate a random melody based on a given key and chord progression.
    The melody starts with a motif, then for each subsequent note, candidate notes from the current chord 
    are evaluated for closeness in interval to the previous note. Candidates within (min_interval + 1 semitone)
    are collected and one is chosen at random. If no candidate is found, a fallback note from the key is used.

    Args:
        key (str): Musical key.
        num_notes (int): Total number of notes in the melody.
        chord_progression (List[str]): Chord progression.
        motif_length (int, optional): Length of the initial motif. Defaults to 4.

    Returns:
        List[str]: Generated melody as a list of note names.
    """
    if num_notes < motif_length:
        raise ValueError("num_notes must be greater than or equal to motif_length")

    notes_in_key = SCALE[key]
    # Generate the initial motif.
    melody = generate_motif(motif_length, key)

    for i in range(motif_length, num_notes):
        chord = chord_progression[i % len(chord_progression)]
        chord_notes = get_chord_notes(chord)
        prev_note = melody[-1]
        candidates = []
        min_interval = None

        # Determine the smallest interval from the previous note for notes in the chord.
        for note in notes_in_key:
            for octave in range(4, 7):  # Consider octaves 4 through 6
                candidate_note = note + str(octave)
                if note in chord_notes:
                    interval = get_interval(prev_note, candidate_note)
                    if min_interval is None or interval < min_interval:
                        min_interval = interval

        # Collect candidates within a threshold (min_interval + 1 semitone).
        if min_interval is not None:
            threshold = min_interval + 1
            for note in notes_in_key:
                for octave in range(4, 7):
                    candidate_note = note + str(octave)
                    if note in chord_notes:
                        interval = get_interval(prev_note, candidate_note)
                        if interval <= threshold:
                            candidates.append(candidate_note)

        # Fallback: If no candidates are found, choose a random note from the key.
        if not candidates:
            logging.warning(f"No candidate found for chord {chord} with previous note {prev_note}. Using fallback.")
            fallback_note = random.choice(notes_in_key) + str(random.randint(4, 6))
            candidates.append(fallback_note)

        next_note = random.choice(candidates)
        melody.append(next_note)

    return melody

def create_midi_file(melody: List[str], bpm: int, time_signature: Tuple[int, int], output_file: str) -> None:
    """
    Create a MIDI file for the given melody, BPM, and time signature.
    This function assigns note durations based on a randomly chosen rhythmic pattern.

    Args:
        melody (List[str]): List of note names.
        bpm (int): Beats per minute.
        time_signature (Tuple[int, int]): Time signature (numerator, denominator).
        output_file (str): Path for saving the MIDI file.
    """
    ticks_per_beat = 480
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    # Set tempo and time signature.
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    track.append(mido.MetaMessage('time_signature', numerator=time_signature[0], denominator=time_signature[1]))

    # Select a rhythmic pattern and compute the duration of a whole note in ticks.
    pattern = random.choice(PATTERNS)
    whole_note_ticks = ticks_per_beat * 4

    # Generate MIDI events for each note using the rhythmic pattern cyclically.
    for i, note in enumerate(melody):
        duration_fraction = pattern[i % len(pattern)]
        note_duration = int(duration_fraction * whole_note_ticks)
        midi_note = note_to_midi(note)
        note_on = Message('note_on', note=midi_note, velocity=64, time=0)
        note_off = Message('note_off', note=midi_note, velocity=64, time=note_duration)
        track.append(note_on)
        track.append(note_off)

    mid.save(output_file)
    logging.info(f"MIDI file saved to {output_file}")

def run_cli() -> None:
    """
    Run the command-line interface for melody generation.
    """
    parser = argparse.ArgumentParser(description="Generate a random melody and save as a MIDI file.")
    parser.add_argument('--key', type=str, required=True, help="Musical key (e.g., C, Dm, etc.).")
    parser.add_argument('--chords', type=str, required=True, help="Comma-separated chord progression (e.g., C,Am,F,G).")
    parser.add_argument('--bpm', type=int, required=True, help="Beats per minute (integer).")
    parser.add_argument('--timesig', type=str, required=True, help="Time signature in numerator/denominator format (e.g., 4/4).")
    parser.add_argument('--notes', type=int, required=True, help="Number of notes in the melody.")
    parser.add_argument('--output', type=str, required=True, help="Output MIDI file path.")
    parser.add_argument('--motif_length', type=int, default=4, help="Length of the initial motif (default: 4).")
    args = parser.parse_args()

    # Validate key and chord progression.
    if args.key not in SCALE:
        logging.error("Invalid key provided.")
        sys.exit(1)

    chord_progression = [chord.strip() for chord in args.chords.split(',')]
    for chord in chord_progression:
        if chord not in CHORDS:
            logging.error(f"Invalid chord in progression: {chord}")
            sys.exit(1)

    try:
        numerator, denominator = map(int, args.timesig.split('/'))
    except Exception:
        logging.error("Time signature must be in the format 'numerator/denominator' (e.g., 4/4).")
        sys.exit(1)

    melody = generate_melody(args.key, args.notes, chord_progression, motif_length=args.motif_length)
    create_midi_file(melody, args.bpm, (numerator, denominator), args.output)
    logging.info("Melody generation complete.")

def run_gui() -> None:
    """
    Run the graphical user interface (GUI) for melody generation using tkinter.
    """
    root = tk.Tk()
    root.title("Melody Generator")

    # Create a frame to hold input widgets.
    frame = tk.Frame(root, padx=10, pady=10)
    frame.grid(row=0, column=0)

    # Key selection using a drop-down (Combobox).
    key_label = tk.Label(frame, text="Key:")
    key_label.grid(row=0, column=0, sticky='w')
    key_var = tk.StringVar()
    key_combobox = ttk.Combobox(frame, textvariable=key_var, values=list(SCALE.keys()), state='readonly')
    key_combobox.grid(row=0, column=1)
    key_combobox.current(0)

    # Chord progression selection using a multi-select listbox.
    chord_label = tk.Label(frame, text="Chord Progression (Select multiple):")
    chord_label.grid(row=1, column=0, sticky='w')
    chord_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10)
    sorted_chords = sorted(CHORDS.keys())
    for chord in sorted_chords:
        chord_listbox.insert(tk.END, chord)
    chord_listbox.grid(row=1, column=1)

    # BPM entry.
    bpm_label = tk.Label(frame, text="BPM:")
    bpm_label.grid(row=2, column=0, sticky='w')
    bpm_entry = tk.Entry(frame)
    bpm_entry.grid(row=2, column=1)
    bpm_entry.insert(0, "120")

    # Time Signature entry.
    timesig_label = tk.Label(frame, text="Time Signature (e.g., 4/4):")
    timesig_label.grid(row=3, column=0, sticky='w')
    timesig_entry = tk.Entry(frame)
    timesig_entry.grid(row=3, column=1)
    timesig_entry.insert(0, "4/4")

    # Number of notes entry.
    notes_label = tk.Label(frame, text="Number of notes:")
    notes_label.grid(row=4, column=0, sticky='w')
    notes_entry = tk.Entry(frame)
    notes_entry.grid(row=4, column=1)
    notes_entry.insert(0, "16")

    # Motif length entry.
    motif_label = tk.Label(frame, text="Motif Length:")
    motif_label.grid(row=5, column=0, sticky='w')
    motif_entry = tk.Entry(frame)
    motif_entry.grid(row=5, column=1)
    motif_entry.insert(0, "4")

    def generate_button_click() -> None:
        """
        Callback when 'Generate Melody' is clicked.
        Validates input, generates the melody, and saves the MIDI file.
        """
        key = key_var.get()
        selected_indices = chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Input Error", "Please select at least one chord for the progression.")
            return
        chord_progression = [chord_listbox.get(i) for i in selected_indices]
        try:
            bpm = int(bpm_entry.get())
            notes_count = int(notes_entry.get())
            motif_length = int(motif_entry.get())
            timesig_parts = timesig_entry.get().split('/')
            if len(timesig_parts) != 2:
                raise ValueError
            numerator, denominator = map(int, timesig_parts)
        except ValueError:
            messagebox.showerror("Input Error", "Ensure BPM, Number of Notes, and Motif Length are integers and Time Signature is formatted as 'numerator/denominator'.")
            return

        output_file = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if output_file:
            melody = generate_melody(key, notes_count, chord_progression, motif_length=motif_length)
            create_midi_file(melody, bpm, (numerator, denominator), output_file)
            messagebox.showinfo("Success", f"MIDI file saved to {output_file}")

    # Generate Melody button.
    generate_button = tk.Button(frame, text="Generate Melody", command=generate_button_click)
    generate_button.grid(row=6, column=0, columnspan=2, pady=10)

    root.mainloop()

def main() -> None:
    """
    Main entry point. Runs the CLI if arguments are provided; otherwise, launches the GUI.
    """
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()

if __name__ == '__main__':
    main()

