"""Tkinter GUI front-end for the Melody Generator application.

This module contains :class:`MelodyGeneratorGUI`, a thin wrapper around the
core melody functions that exposes them through a simple Tkinter interface.
All user interaction and validation logic lives here while the heavy lifting
is delegated to :mod:`melody_generator`.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Tuple, Dict, Optional
import os
import subprocess
import sys
from tempfile import NamedTemporaryFile

from . import diatonic_chords

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
        harmony_line_fn: Optional[Callable[[List[str]], List[str]]] = None,
        counterpoint_fn: Optional[Callable[[List[str], str], List[str]]] = None,
    ) -> None:
        """Initialize the GUI and create all widgets.

        Parameters mirror the core melody functions so the GUI can
        delegate work to them. Optional callbacks are used for loading
        and saving user preferences as well as generating random chords
        or rhythms.
        """
        self.generate_melody = generate_melody
        self.create_midi_file = create_midi_file
        self.scale = scale
        self.chords = chords
        self.load_settings = load_settings
        self.save_settings = save_settings
        self.random_chords_fn = random_chords_fn
        self.random_rhythm_fn = random_rhythm_fn
        self.harmony_line_fn = harmony_line_fn
        self.counterpoint_fn = counterpoint_fn

        self.rhythm_pattern: Optional[List[float]] = None

        self.root = tk.Tk()
        self.root.title("Melody Generator")

        self._setup_theme()
        self._build_widgets()
        # Apply theme again so newly created widgets inherit colors
        self._apply_theme()

    def _setup_theme(self) -> None:
        """Configure ttk theme and basic colors."""
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            # fall back to default
            pass

        self.dark_mode = True
        self.root.option_add("*Font", "Helvetica 10")
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply styling based on ``self.dark_mode``."""
        if self.dark_mode:
            self.bg_color = "#2E1A47"
            fg = "white"
            btn_bg = "#4B0082"
        else:
            self.bg_color = "#FFFFFF"
            fg = "black"
            btn_bg = "#E0E0E0"

        self.root.configure(bg=self.bg_color)
        for name in ("TFrame", "TLabel", "TCheckbutton"):
            self.style.configure(name, background=self.bg_color, foreground=fg)
        self.style.configure("TButton", background=btn_bg, foreground=fg)
        self.style.configure("TEntry", fieldbackground="white", foreground=fg)
        if hasattr(self, "chord_listbox"):
            if self.dark_mode:
                self.chord_listbox.configure(bg="black", fg="white")
            else:
                self.chord_listbox.configure(bg="white", fg="black")

    def _toggle_theme(self) -> None:
        """Switch between dark and light color schemes."""
        self.dark_mode = bool(self.theme_var.get())
        self._apply_theme()

    def _create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Attach a simple tooltip to ``widget``."""
        tooltip: Optional[tk.Toplevel] = None

        def show(_event: tk.Event) -> None:
            """Display the tooltip window next to the widget."""

            nonlocal tooltip
            if tooltip is not None:
                return
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            tooltip.wm_geometry(f"+{x}+{y}")
            ttk.Label(tooltip, text=text, background="yellow").pack(ipadx=2)

        def hide(_event: tk.Event) -> None:
            """Remove the tooltip when the pointer leaves the widget."""

            nonlocal tooltip
            if tooltip is not None:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _update_chord_list(self) -> None:
        """Refresh the chord list based on the selected key."""

        chords = diatonic_chords(self.key_var.get())
        self.chord_listbox.delete(0, tk.END)
        self.sorted_chords = sorted(chords)
        for chord in self.sorted_chords:
            self.chord_listbox.insert(tk.END, chord)

    def _build_widgets(self) -> None:
        """Create all GUI widgets and arrange them on the window."""
        frame = ttk.Frame(self.root, padding=(10, 10))
        frame.grid(row=0, column=0)

        # Key selection
        ttk.Label(frame, text="Key:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        key_combobox = ttk.Combobox(
            frame, textvariable=self.key_var, values=list(self.scale.keys()), state="readonly"
        )
        key_combobox.grid(row=0, column=1)
        key_combobox.current(0)
        key_combobox.bind("<<ComboboxSelected>>", lambda _e: self._update_chord_list())

        # Chord progression listbox
        ttk.Label(frame, text="Chord Progression (Select multiple):").grid(row=1, column=0, sticky="w")
        self.chord_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10, bg="white")
        self._update_chord_list()
        self.chord_listbox.grid(row=1, column=1)

        # BPM slider
        ttk.Label(frame, text="BPM:").grid(row=2, column=0, sticky="w")
        self.bpm_var = tk.IntVar(value=120)
        bpm_scale = ttk.Scale(
            frame,
            from_=40,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.bpm_var,
        )
        bpm_scale.grid(row=2, column=1)
        self._create_tooltip(bpm_scale, "Beats per minute")

        # Time signature dropdown
        ttk.Label(frame, text="Time Signature:").grid(row=3, column=0, sticky="w")
        self.timesig_var = tk.StringVar(value="4/4")
        timesig_box = ttk.Combobox(
            frame,
            textvariable=self.timesig_var,
            values=["2/4", "3/4", "4/4", "6/8"],
            state="readonly",
        )
        timesig_box.grid(row=3, column=1)
        self._create_tooltip(timesig_box, "Time signature of the piece")

        # Number of notes slider
        ttk.Label(frame, text="Number of notes:").grid(row=4, column=0, sticky="w")
        self.notes_var = tk.IntVar(value=16)
        ttk.Scale(
            frame,
            from_=8,
            to=64,
            orient=tk.HORIZONTAL,
            variable=self.notes_var,
        ).grid(row=4, column=1)

        # Motif length entry
        ttk.Label(frame, text="Motif Length:").grid(row=5, column=0, sticky="w")
        self.motif_entry = ttk.Entry(frame)
        self.motif_entry.grid(row=5, column=1)
        self._create_tooltip(self.motif_entry, "Length of repeating motif")
        self.motif_entry.insert(0, "4")

        # Harmony checkbox
        self.harmony_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Add Harmony",
            variable=self.harmony_var,
        ).grid(row=6, column=0, columnspan=2)

        self.counterpoint_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Add Counterpoint",
            variable=self.counterpoint_var,
        ).grid(row=7, column=0, columnspan=2)

        ttk.Label(frame, text="Harmony Lines:").grid(row=8, column=0, sticky="w")
        self.harmony_lines = tk.Entry(frame)
        self.harmony_lines.insert(0, "0")
        self.harmony_lines.grid(row=8, column=1)

        # Randomize buttons
        ttk.Button(
            frame,
            text="Randomize Chords",
            command=self._randomize_chords,
        ).grid(row=9, column=0, columnspan=2, pady=(5, 0))
        ttk.Button(
            frame,
            text="Randomize Rhythm",
            command=self._randomize_rhythm,
        ).grid(row=10, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(
            frame,
            text="Load Preferences",
            command=self._load_preferences,
        ).grid(row=11, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(
            frame,
            text="Preview Melody",
            command=self._preview_button_click,
        ).grid(row=12, column=0, columnspan=2, pady=(5, 0))

        # Generate button
        ttk.Button(
            frame,
            text="Generate Melody",
            command=self._generate_button_click,
        ).grid(row=13, column=0, columnspan=2, pady=10)

        self.theme_var = tk.BooleanVar(value=self.dark_mode)
        ttk.Checkbutton(
            frame,
            text="Toggle Dark Mode",
            command=self._toggle_theme,
            variable=self.theme_var,
        ).grid(row=14, column=0, columnspan=2, pady=(5, 0))

        # Apply persisted settings if available
        if self.load_settings is not None:
            self._apply_settings(self.load_settings())

    def _generate_button_click(self) -> None:
        """Validate inputs and generate a MIDI file from the selections."""
        key = self.key_var.get()
        selected_indices = self.chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Input Error", "Please select at least one chord for the progression.")
            return
        # Build the chord progression from the selected listbox entries
        chord_progression = [self.chord_listbox.get(i) for i in selected_indices]
        try:
            bpm = self.bpm_var.get()
            notes_count = self.notes_var.get()
            motif_length = int(self.motif_entry.get())
            if bpm <= 0 or notes_count <= 0 or motif_length <= 0:
                raise ValueError
            ts_parts = self.timesig_var.get().split("/")
            if len(ts_parts) != 2:
                raise ValueError
            numerator, denominator = map(int, ts_parts)
            if numerator <= 0 or denominator <= 0:
                raise ValueError
        except ValueError:
            # Show one error message for any invalid numeric input
            messagebox.showerror(
                "Input Error",
                "Ensure BPM, Number of Notes, and Motif Length are integers and Time Signature is formatted as 'numerator/denominator'.",
            )
            return

        if motif_length > notes_count:
            messagebox.showerror(
                "Input Error",
                "Motif length cannot exceed the number of notes."
            )
            return

        output_file = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI files", "*.mid")])
        if output_file:
            melody = self.generate_melody(key, notes_count, chord_progression, motif_length=motif_length)
            extra: List[List[str]] = []
            if self.harmony_line_fn is not None:
                try:
                    lines = int(self.harmony_lines.get() or 0)
                except ValueError:
                    lines = 0
                # Generate the requested number of harmony tracks
                for _ in range(max(0, lines)):
                    extra.append(self.harmony_line_fn(melody))
            if self.counterpoint_fn is not None and self.counterpoint_var.get():
                # Optionally add a counterpoint melody line
                extra.append(self.counterpoint_fn(melody, key))
            self.create_midi_file(
                melody,
                bpm,
                (numerator, denominator),
                output_file,
                harmony=self.harmony_var.get(),
                pattern=self.rhythm_pattern,
                extra_tracks=extra,
            )
            messagebox.showinfo("Success", f"MIDI file saved to {output_file}")
            if self.save_settings is not None and messagebox.askyesno(
                "Save Preferences", "Save these settings as defaults?"
            ):
                self.save_settings(self._collect_settings())

    def _preview_button_click(self) -> None:
        """Play the generated melody in the default MIDI player."""
        key = self.key_var.get()
        selected_indices = self.chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror(
                "Input Error", "Please select at least one chord for the progression."
            )
            return
        chords = [self.chord_listbox.get(i) for i in selected_indices]
        try:
            bpm = self.bpm_var.get()
            notes_count = self.notes_var.get()
            motif_length = int(self.motif_entry.get())
            if bpm <= 0 or notes_count <= 0 or motif_length <= 0:
                raise ValueError
            ts_parts = self.timesig_var.get().split("/")
            if len(ts_parts) != 2:
                raise ValueError
            numerator, denominator = map(int, ts_parts)
            if numerator <= 0 or denominator <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Input Error",
                "Ensure BPM, Number of Notes, and Motif Length are integers and Time Signature is formatted as 'numerator/denominator'.",
            )
            return

        if motif_length > notes_count:
            messagebox.showerror(
                "Input Error", "Motif length cannot exceed the number of notes."
            )
            return

        melody = self.generate_melody(key, notes_count, chords, motif_length=motif_length)
        extra: List[List[str]] = []
        if self.harmony_line_fn is not None:
            try:
                lines = int(self.harmony_lines.get() or 0)
            except ValueError:
                lines = 0
            for _ in range(max(0, lines)):
                extra.append(self.harmony_line_fn(melody))
        if self.counterpoint_fn is not None and self.counterpoint_var.get():
            extra.append(self.counterpoint_fn(melody, key))
        tmp = NamedTemporaryFile(suffix=".mid", delete=False)
        tmp_path = tmp.name
        tmp.close()
        self.create_midi_file(
            melody,
            bpm,
            (numerator, denominator),
            tmp_path,
            harmony=self.harmony_var.get(),
            pattern=self.rhythm_pattern,
            extra_tracks=extra,
        )
        try:
            if sys.platform.startswith("win"):
                os.startfile(tmp_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", tmp_path])
            else:
                subprocess.Popen(["xdg-open", tmp_path])
        except Exception as exc:
            messagebox.showerror("Preview Error", f"Could not open MIDI file: {exc}")

    def _randomize_chords(self) -> None:
        """Select a random chord progression and apply it to the list box."""
        if self.random_chords_fn is None:
            return
        progression = self.random_chords_fn(self.key_var.get(), 4)
        self.chord_listbox.selection_clear(0, tk.END)
        for chord in progression:
            if chord in self.sorted_chords:
                idx = self.sorted_chords.index(chord)
                # Highlight each chord in the listbox
                self.chord_listbox.selection_set(idx)

    def _randomize_rhythm(self) -> None:
        """Create a random rhythm pattern and store it for generation."""
        if self.random_rhythm_fn is None:
            return
        # Store the newly generated pattern for use during MIDI export
        self.rhythm_pattern = self.random_rhythm_fn()

    def _load_preferences(self) -> None:
        """Reload settings from disk and apply them to the widgets."""
        if self.load_settings is None:
            return
        self._apply_settings(self.load_settings())

    def run(self) -> None:
        """Start the Tk event loop to display the window."""
        # Hand control over to Tkinter so the application becomes interactive.
        # This call blocks until the window is closed.
        self.root.mainloop()

    def _collect_settings(self) -> Dict:
        """Gather current widget values into a dictionary."""
        # Persist any chords currently selected in the listbox
        chords = [self.chord_listbox.get(i) for i in self.chord_listbox.curselection()]
        return {
            "key": self.key_var.get(),
            "bpm": self.bpm_var.get(),
            "timesig": self.timesig_var.get(),
            "notes": self.notes_var.get(),
            "motif_length": int(self.motif_entry.get() or 0),
            "harmony": self.harmony_var.get(),
            "counterpoint": self.counterpoint_var.get(),
            "harmony_lines": int(self.harmony_lines.get() or 0),
            "chords": chords,
        }

    def _apply_settings(self, settings: Dict) -> None:
        """Set widget values based on ``settings`` dictionary."""
        # Ignore empty dictionaries to avoid resetting controls unnecessarily
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
        if "counterpoint" in settings:
            self.counterpoint_var.set(settings["counterpoint"])
        if "harmony_lines" in settings:
            self.harmony_lines.delete(0, tk.END)
            self.harmony_lines.insert(0, str(settings["harmony_lines"]))
        self._update_chord_list()
        chords = settings.get("chords")
        if chords:
            self.chord_listbox.selection_clear(0, tk.END)
            for chord in chords:
                if chord in self.sorted_chords:
                    idx = self.sorted_chords.index(chord)
                    # Restore selection state for each saved chord
                    self.chord_listbox.selection_set(idx)
