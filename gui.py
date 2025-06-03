# GUI module for Melody Generator
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Tuple, Dict

class MelodyGeneratorGUI:
    """Tkinter-based GUI for melody generation."""

    def __init__(
        self,
        generate_melody: Callable[[str, int, List[str], int], List[str]],
        create_midi_file: Callable[[List[str], int, Tuple[int, int], str, bool], None],
        scale: Dict[str, List[str]],
        chords: Dict[str, List[str]],
    ) -> None:
        self.generate_melody = generate_melody
        self.create_midi_file = create_midi_file
        self.scale = scale
        self.chords = chords

        self.root = tk.Tk()
        self.root.title("Melody Generator")

        self._build_widgets()

    def _build_widgets(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.grid(row=0, column=0)

        # Key selection
        tk.Label(frame, text="Key:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        key_combobox = ttk.Combobox(
            frame, textvariable=self.key_var, values=list(self.scale.keys()), state="readonly"
        )
        key_combobox.grid(row=0, column=1)
        key_combobox.current(0)

        # Chord progression listbox
        tk.Label(frame, text="Chord Progression (Select multiple):").grid(row=1, column=0, sticky="w")
        self.chord_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10)
        for chord in sorted(self.chords.keys()):
            self.chord_listbox.insert(tk.END, chord)
        self.chord_listbox.grid(row=1, column=1)

        # BPM slider
        tk.Label(frame, text="BPM:").grid(row=2, column=0, sticky="w")
        self.bpm_var = tk.IntVar(value=120)
        tk.Scale(frame, from_=40, to=200, orient=tk.HORIZONTAL, variable=self.bpm_var).grid(row=2, column=1)

        # Time signature dropdown
        tk.Label(frame, text="Time Signature:").grid(row=3, column=0, sticky="w")
        self.timesig_var = tk.StringVar(value="4/4")
        ttk.Combobox(
            frame,
            textvariable=self.timesig_var,
            values=["2/4", "3/4", "4/4", "6/8"],
            state="readonly",
        ).grid(row=3, column=1)

        # Number of notes slider
        tk.Label(frame, text="Number of notes:").grid(row=4, column=0, sticky="w")
        self.notes_var = tk.IntVar(value=16)
        tk.Scale(frame, from_=8, to=64, orient=tk.HORIZONTAL, variable=self.notes_var).grid(row=4, column=1)

        # Motif length entry
        tk.Label(frame, text="Motif Length:").grid(row=5, column=0, sticky="w")
        self.motif_entry = tk.Entry(frame)
        self.motif_entry.grid(row=5, column=1)
        self.motif_entry.insert(0, "4")

        # Harmony checkbox
        self.harmony_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Add Harmony", variable=self.harmony_var).grid(row=6, column=0, columnspan=2)

        # Generate button
        tk.Button(frame, text="Generate Melody", command=self._generate_button_click).grid(
            row=7, column=0, columnspan=2, pady=10
        )

    def _generate_button_click(self) -> None:
        key = self.key_var.get()
        selected_indices = self.chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Input Error", "Please select at least one chord for the progression.")
            return
        chord_progression = [self.chord_listbox.get(i) for i in selected_indices]
        try:
            bpm = self.bpm_var.get()
            notes_count = self.notes_var.get()
            motif_length = int(self.motif_entry.get())
            ts_parts = self.timesig_var.get().split("/")
            if len(ts_parts) != 2:
                raise ValueError
            numerator, denominator = map(int, ts_parts)
        except ValueError:
            messagebox.showerror(
                "Input Error",
                "Ensure BPM, Number of Notes, and Motif Length are integers and Time Signature is formatted as 'numerator/denominator'.",
            )
            return

        output_file = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if output_file:
            melody = self.generate_melody(key, notes_count, chord_progression, motif_length=motif_length)
            self.create_midi_file(
                melody,
                bpm,
                (numerator, denominator),
                output_file,
                harmony=self.harmony_var.get(),
            )
            messagebox.showinfo("Success", f"MIDI file saved to {output_file}")

    def run(self) -> None:
        self.root.mainloop()
