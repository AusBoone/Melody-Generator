# GUI module for Melody Generator
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Tuple, Dict, Optional

class MelodyGeneratorGUI:
    """Tkinter-based GUI for melody generation."""

    def __init__(
        self,
        generate_melody: Callable[[str, int, List[str], int], List[str]],
        create_midi_file: Callable[[List[str], int, Tuple[int, int], str, bool, Optional[List[float]]], None],
        scale: Dict[str, List[str]],
        chords: Dict[str, List[str]],
        load_settings: Optional[Callable[[], Dict]] = None,
        save_settings: Optional[Callable[[Dict], None]] = None,
        random_chords_fn: Optional[Callable[[str, int], List[str]]] = None,
        random_rhythm_fn: Optional[Callable[[], List[float]]] = None,
    ) -> None:
        self.generate_melody = generate_melody
        self.create_midi_file = create_midi_file
        self.scale = scale
        self.chords = chords
        self.load_settings = load_settings
        self.save_settings = save_settings
        self.random_chords_fn = random_chords_fn
        self.random_rhythm_fn = random_rhythm_fn

        self.rhythm_pattern: Optional[List[float]] = None

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
        self.sorted_chords = sorted(self.chords.keys())
        for chord in self.sorted_chords:
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

        # Randomize buttons
        tk.Button(frame, text="Randomize Chords", command=self._randomize_chords).grid(
            row=7, column=0, columnspan=2, pady=(5, 0)
        )
        tk.Button(frame, text="Randomize Rhythm", command=self._randomize_rhythm).grid(
            row=8, column=0, columnspan=2, pady=(5, 0)
        )

        # Generate button
        tk.Button(frame, text="Generate Melody", command=self._generate_button_click).grid(
            row=9, column=0, columnspan=2, pady=10
        )

        # Apply persisted settings if available
        if self.load_settings is not None:
            self._apply_settings(self.load_settings())

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
                pattern=self.rhythm_pattern,
            )
            messagebox.showinfo("Success", f"MIDI file saved to {output_file}")
            if self.save_settings is not None and messagebox.askyesno(
                "Save Preferences", "Save these settings as defaults?"
            ):
                self.save_settings(self._collect_settings())

    def _randomize_chords(self) -> None:
        if self.random_chords_fn is None:
            return
        progression = self.random_chords_fn(self.key_var.get(), 4)
        self.chord_listbox.selection_clear(0, tk.END)
        for chord in progression:
            if chord in self.sorted_chords:
                idx = self.sorted_chords.index(chord)
                self.chord_listbox.selection_set(idx)

    def _randomize_rhythm(self) -> None:
        if self.random_rhythm_fn is None:
            return
        self.rhythm_pattern = self.random_rhythm_fn()

    def run(self) -> None:
        self.root.mainloop()

    def _collect_settings(self) -> Dict:
        """Gather current widget values into a dictionary."""
        chords = [self.chord_listbox.get(i) for i in self.chord_listbox.curselection()]
        return {
            "key": self.key_var.get(),
            "bpm": self.bpm_var.get(),
            "timesig": self.timesig_var.get(),
            "notes": self.notes_var.get(),
            "motif_length": int(self.motif_entry.get() or 0),
            "harmony": self.harmony_var.get(),
            "chords": chords,
        }

    def _apply_settings(self, settings: Dict) -> None:
        """Set widget values based on ``settings`` dictionary."""
        if not settings:
            return
        self.key_var.set(settings.get("key", self.key_var.get()))
        if "bpm" in settings:
            self.bpm_var.set(settings["bpm"])
        if "timesig" in settings:
            self.timesig_var.set(settings["timesig"])
        if "notes" in settings:
            self.notes_var.set(settings["notes"])
        if "motif_length" in settings:
            self.motif_entry.delete(0, tk.END)
            self.motif_entry.insert(0, str(settings["motif_length"]))
        if "harmony" in settings:
            self.harmony_var.set(settings["harmony"])
        chords = settings.get("chords")
        if chords:
            self.chord_listbox.selection_clear(0, tk.END)
            for chord in chords:
                if chord in self.sorted_chords:
                    idx = self.sorted_chords.index(chord)
                    self.chord_listbox.selection_set(idx)
