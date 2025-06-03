"""GUI for Melody Generator"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List

from melody_generator import (
    SCALE,
    CHORDS,
    generate_melody,
    create_midi_file,
)

class MelodyGeneratorGUI:
    """Encapsulates the tkinter GUI logic."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Melody Generator")
        self._build_widgets()

    def _build_widgets(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.grid(row=0, column=0)

        # Key
        tk.Label(frame, text="Key:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar(value=list(SCALE.keys())[0])
        key_combo = ttk.Combobox(frame, textvariable=self.key_var, values=list(SCALE.keys()), state="readonly")
        key_combo.grid(row=0, column=1)

        # Chord progression
        tk.Label(frame, text="Chord Progression (Select multiple):").grid(row=1, column=0, sticky="w")
        self.chord_list = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10)
        for chord in sorted(CHORDS.keys()):
            self.chord_list.insert(tk.END, chord)
        self.chord_list.grid(row=1, column=1)

        # BPM
        tk.Label(frame, text="BPM:").grid(row=2, column=0, sticky="w")
        self.bpm_var = tk.IntVar(value=120)
        tk.Scale(frame, from_=40, to=200, orient=tk.HORIZONTAL, variable=self.bpm_var).grid(row=2, column=1)

        # Time signature
        tk.Label(frame, text="Time Signature:").grid(row=3, column=0, sticky="w")
        self.timesig_var = tk.StringVar(value="4/4")
        ttk.Combobox(frame, textvariable=self.timesig_var, values=["2/4", "3/4", "4/4", "6/8"], state="readonly").grid(row=3, column=1)

        # Number of notes
        tk.Label(frame, text="Number of notes:").grid(row=4, column=0, sticky="w")
        self.notes_var = tk.IntVar(value=16)
        tk.Scale(frame, from_=8, to=64, orient=tk.HORIZONTAL, variable=self.notes_var).grid(row=4, column=1)

        # Motif length
        tk.Label(frame, text="Motif Length:").grid(row=5, column=0, sticky="w")
        self.motif_entry = tk.Entry(frame)
        self.motif_entry.insert(0, "4")
        self.motif_entry.grid(row=5, column=1)

        # Harmony checkbox
        self.harmony_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Add Harmony", variable=self.harmony_var).grid(row=6, column=0, columnspan=2)

        tk.Button(frame, text="Generate Melody", command=self._on_generate).grid(row=7, column=0, columnspan=2, pady=10)

    def _validate_inputs(self) -> tuple[int, int, int, int]:
        """Validate and parse numeric inputs."""
        try:
            bpm = int(self.bpm_var.get())
            notes_count = int(self.notes_var.get())
            motif_length = int(self.motif_entry.get())
            numerator, denominator = map(int, self.timesig_var.get().split("/"))
        except Exception:
            raise ValueError("Ensure BPM, Number of Notes, Motif Length, and Time Signature are valid integers.")

        if bpm <= 0:
            raise ValueError("BPM must be positive.")
        if notes_count <= 0:
            raise ValueError("Number of notes must be positive.")
        if motif_length <= 0 or motif_length > notes_count:
            raise ValueError("Motif Length must be positive and no greater than Number of notes.")
        if numerator <= 0 or denominator not in {1, 2, 4, 8, 16}:
            raise ValueError("Unsupported time signature.")
        return bpm, notes_count, motif_length, numerator, denominator

    def _on_generate(self) -> None:
        key = self.key_var.get()
        selected = self.chord_list.curselection()
        if not selected:
            messagebox.showerror("Input Error", "Please select at least one chord for the progression.")
            return
        chords = [self.chord_list.get(i) for i in selected]

        try:
            bpm, notes_count, motif_length, numerator, denominator = self._validate_inputs()
        except ValueError as exc:
            messagebox.showerror("Input Error", str(exc))
            return

        outfile = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if outfile:
            melody = generate_melody(key, notes_count, chords, motif_length=motif_length)
            create_midi_file(melody, bpm, (numerator, denominator), outfile, harmony=self.harmony_var.get())
            messagebox.showinfo("Success", f"MIDI file saved to {outfile}")

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    MelodyGeneratorGUI().run()
