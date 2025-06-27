"""Tkinter GUI front-end for the Melody Generator application.

This module contains :class:`MelodyGeneratorGUI`, a thin wrapper around the
core melody functions that exposes them through a simple Tkinter interface.
All user interaction and validation logic lives here while the heavy lifting
is delegated to :mod:`melody_generator`.
"""

# ---------------------------------------------------------------
# Modification Summary
# ---------------------------------------------------------------
# * ``_open_default_player`` now runs the system player via ``subprocess.run``
#   inside a daemon thread and optionally removes the file when done.
#   ``_preview_button_click`` was updated to rely on this logic, preventing
#   premature deletion of the preview MIDI file when FluidSynth is missing.
# * Numeric entries for motif length and harmony lines now use ``ttk.Spinbox``
#   with range validation.
# * ``_check_preview_available`` displays a notice when FluidSynth or a
#   SoundFont is unavailable for preview playback.
# * ``_generate_button_click`` now validates ``base_octave`` to ensure it
#   stays within the MIDI range 0-8 before generating a melody.
# ---------------------------------------------------------------
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Tuple, Dict, Optional
import os
import subprocess
import sys
import threading
from tempfile import NamedTemporaryFile

from . import diatonic_chords

# ``MidiPlaybackError`` signals that preview playback failed within the
# ``playback`` helper module. Catching it allows the GUI to fall back to the
# system default player without masking unrelated errors.
from .playback import MidiPlaybackError

# Mapping of display names to General MIDI program numbers used by the
# instrument selector. Only a small subset is provided for demonstration
# purposes.
INSTRUMENTS = {
    "Piano": 0,
    "Guitar": 24,
    "Bass": 32,
    "Violin": 40,
    "Flute": 73,
}


class MelodyGeneratorGUI:
    """Tkinter-based GUI for melody generation."""

    def __init__(
        self,
        generate_melody: Callable[[str, int, List[str], int, int], List[str]],
        create_midi_file: Callable[
            [
                List[str],
                int,
                Tuple[int, int],
                str,
                bool,
                Optional[List[float]],
                Optional[List[List[str]]],
                Optional[List[str]],
                bool,
                int,
            ],
            None,
        ],
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

        @param generate_melody: Function to create melodies.
        @param create_midi_file: Function to write MIDI files.
        @param scale: Mapping of keys to scale notes.
        @param chords: Mapping of chord names to notes.
        @param load_settings: Optional loader for saved preferences.
        @param save_settings: Optional saver for user preferences.
        @param random_chords_fn: Optional callback to pick chords.
        @param random_rhythm_fn: Optional callback for rhythm patterns.
        @param harmony_line_fn: Optional harmony generator.
        @param counterpoint_fn: Optional counterpoint generator.
        @returns None: GUI is prepared for display.
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
        self._check_preview_available()

    def _setup_theme(self) -> None:
        """Configure ttk theme and basic colors.

        @returns None: Theme information is stored on the instance.
        """
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
        """Apply styling based on ``self.dark_mode``.

        @returns None: Widgets are updated in place.
        """
        if self.dark_mode:
            self.bg_color = "#2E1A47"
            fg = "white"
            btn_bg = "#4B0082"
        else:
            self.bg_color = "#FFFFFF"
            fg = "black"
            btn_bg = "#E0E0E0"

        self.root.configure(bg=self.bg_color)
        # Apply colours to a small set of common widget classes so every part
        # of the interface adopts the selected theme.
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
        """Switch between dark and light color schemes.

        @returns None: Triggers a theme update.
        """
        self.dark_mode = bool(self.theme_var.get())
        self._apply_theme()

    def _create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Attach a simple tooltip to ``widget``.

        @param widget: Tkinter widget that displays the tooltip.
        @param text: Tooltip text.
        @returns None: Event bindings are registered.
        """
        tooltip: Optional[tk.Toplevel] = None

        def show(_event: tk.Event) -> None:
            """Display the tooltip window next to the widget.

            @returns None: Tooltip window is created if needed.
            """

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
            """Remove the tooltip when the pointer leaves the widget.

            @returns None: Tooltip window is destroyed.
            """

            nonlocal tooltip
            if tooltip is not None:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _update_bpm_label(self, value: str | int) -> None:
        """Display the current BPM next to the slider.

        @param value: Slider value to display.
        @returns None: BPM label text is updated.
        """
        self.bpm_label.config(text=str(int(float(value))))

    def _update_notes_label(self, value: str | int) -> None:
        """Display the current number of notes next to the slider.

        @param value: Slider value to display.
        @returns None: Notes label text is updated.
        """
        self.notes_label.config(text=str(int(float(value))))

    def _update_octave_label(self, value: str | int) -> None:
        """Display the base octave next to its slider.

        @param value: Slider value to display.
        @returns None: Octave label text is updated.
        """
        self.octave_label.config(text=str(int(float(value))))

    def _update_chord_list(self) -> None:
        """Refresh the chord list based on the selected key.

        @returns None: Listbox contents are replaced.
        """

        chords = diatonic_chords(self.key_var.get())
        self.chord_listbox.delete(0, tk.END)
        self.sorted_chords = chords  # preserve degree order
        is_minor = self.key_var.get().endswith("m")
        numerals_major = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
        numerals_minor = ["i", "ii°", "III", "iv", "v", "VI", "VII"]
        numerals = numerals_minor if is_minor else numerals_major
        self.display_map = {}
        for idx, chord in enumerate(self.sorted_chords):
            numeral = numerals[idx % len(numerals)]
            display = f"{numeral}: {chord}"
            self.display_map[display] = chord
            self.chord_listbox.insert(tk.END, display)

    def _check_preview_available(self) -> None:
        """Indicate whether preview playback can function."""
        try:
            from . import playback

            playback._resolve_soundfont(self.soundfont_var.get() or None)
        except Exception:
            self.preview_available = False
            if hasattr(self, "preview_notice"):
                self.preview_notice.config(
                    text="Preview requires FluidSynth and a SoundFont"
                )
        else:
            self.preview_available = True
            if hasattr(self, "preview_notice"):
                self.preview_notice.config(text="")

    def _build_widgets(self) -> None:
        """Create all GUI widgets and arrange them on the window.

        @returns None: Widgets are added to the Tk container.
        """
        frame = ttk.Frame(self.root, padding=(10, 10))
        frame.grid(row=0, column=0)

        # Key selection
        ttk.Label(frame, text="Key:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        key_combobox = ttk.Combobox(
            frame,
            textvariable=self.key_var,
            values=list(self.scale.keys()),
            state="readonly",
        )
        key_combobox.grid(row=0, column=1)
        key_combobox.current(0)
        key_combobox.bind("<<ComboboxSelected>>", lambda _e: self._update_chord_list())

        # Chord progression listbox
        ttk.Label(frame, text="Chord Progression (Select multiple):").grid(
            row=1, column=0, sticky="w"
        )
        self.chord_listbox = tk.Listbox(
            frame, selectmode=tk.MULTIPLE, height=10, bg="white"
        )
        self._update_chord_list()
        self.chord_listbox.grid(row=1, column=1)

        # BPM slider and value label
        ttk.Label(frame, text="BPM:").grid(row=2, column=0, sticky="w")
        self.bpm_var = tk.IntVar(value=120)
        bpm_scale = ttk.Scale(
            frame,
            from_=40,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.bpm_var,
            command=self._update_bpm_label,
        )
        bpm_scale.grid(row=2, column=1)
        self.bpm_label = ttk.Label(frame, text=str(self.bpm_var.get()))
        self.bpm_label.grid(row=2, column=2, padx=(5, 0))
        self._create_tooltip(bpm_scale, "Beats per minute")
        self._update_bpm_label(self.bpm_var.get())

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

        # Number of notes slider and value label
        ttk.Label(frame, text="Number of notes:").grid(row=4, column=0, sticky="w")
        self.notes_var = tk.IntVar(value=16)
        notes_scale = ttk.Scale(
            frame,
            from_=8,
            to=64,
            orient=tk.HORIZONTAL,
            variable=self.notes_var,
            command=self._update_notes_label,
        )
        notes_scale.grid(row=4, column=1)
        self.notes_label = ttk.Label(frame, text=str(self.notes_var.get()))
        self.notes_label.grid(row=4, column=2, padx=(5, 0))
        self._update_notes_label(self.notes_var.get())

        # Base octave slider and label
        ttk.Label(frame, text="Base Octave:").grid(row=5, column=0, sticky="w")
        self.base_octave_var = tk.IntVar(value=4)
        octave_scale = ttk.Scale(
            frame,
            from_=1,
            to=7,
            orient=tk.HORIZONTAL,
            variable=self.base_octave_var,
            command=self._update_octave_label,
        )
        octave_scale.grid(row=5, column=1)
        self.octave_label = ttk.Label(frame, text=str(self.base_octave_var.get()))
        self.octave_label.grid(row=5, column=2, padx=(5, 0))
        self._update_octave_label(self.base_octave_var.get())

        # Instrument selection
        ttk.Label(frame, text="Instrument:").grid(row=6, column=0, sticky="w")
        self.instrument_var = tk.StringVar(value="Piano")
        inst_box = ttk.Combobox(
            frame,
            textvariable=self.instrument_var,
            values=list(INSTRUMENTS.keys()),
            state="readonly",
        )
        inst_box.grid(row=6, column=1)

        # SoundFont selection path used by FluidSynth
        ttk.Label(frame, text="SoundFont:").grid(row=7, column=0, sticky="w")
        self.soundfont_var = tk.StringVar(value=os.environ.get("SOUND_FONT", ""))
        self.soundfont_entry = ttk.Entry(
            frame, textvariable=self.soundfont_var, width=25
        )
        self.soundfont_entry.grid(row=7, column=1)
        ttk.Button(
            frame,
            text="Browse",
            command=self._browse_soundfont,
        ).grid(row=7, column=2, padx=(5, 0))
        # Motif length entry
        ttk.Label(frame, text="Motif Length:").grid(row=8, column=0, sticky="w")
        self.motif_entry = ttk.Spinbox(frame, from_=1, to=32, width=5)
        self.motif_entry.grid(row=8, column=1)
        self._create_tooltip(self.motif_entry, "Length of repeating motif")
        self.motif_entry.set(4)

        # Harmony checkbox
        self.harmony_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Add Harmony",
            variable=self.harmony_var,
        ).grid(row=9, column=0, columnspan=2)

        self.counterpoint_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Add Counterpoint",
            variable=self.counterpoint_var,
        ).grid(row=10, column=0, columnspan=2)

        ttk.Label(frame, text="Harmony Lines:").grid(row=11, column=0, sticky="w")
        self.harmony_lines = ttk.Spinbox(frame, from_=0, to=4, width=5)
        self.harmony_lines.set(0)
        self.harmony_lines.grid(row=11, column=1)

        self.include_chords_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Include Chords",
            variable=self.include_chords_var,
        ).grid(row=12, column=0, columnspan=2)

        self.chords_same_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Merge Chords With Melody",
            variable=self.chords_same_var,
        ).grid(row=13, column=0, columnspan=2)

        # Randomize buttons
        ttk.Button(
            frame,
            text="Randomize Chords",
            command=self._randomize_chords,
        ).grid(row=14, column=0, columnspan=2, pady=(5, 0))
        ttk.Button(
            frame,
            text="Randomize Rhythm",
            command=self._randomize_rhythm,
        ).grid(row=15, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(
            frame,
            text="Load Preferences",
            command=self._load_preferences,
        ).grid(row=16, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(
            frame,
            text="Preview Melody",
            command=self._preview_button_click,
        ).grid(row=17, column=0, columnspan=2, pady=(5, 0))
        self.preview_notice = ttk.Label(
            frame,
            text="",
            foreground="yellow",
        )
        self.preview_notice.grid(row=17, column=2, sticky="w")

        # Generate button
        ttk.Button(
            frame,
            text="Generate Melody",
            command=self._generate_button_click,
        ).grid(row=18, column=0, columnspan=2, pady=10)

        self.theme_var = tk.BooleanVar(value=self.dark_mode)
        ttk.Checkbutton(
            frame,
            text="Toggle Dark Mode",
            command=self._toggle_theme,
            variable=self.theme_var,
        ).grid(row=19, column=0, columnspan=2, pady=(5, 0))

        # Apply persisted settings if available
        if self.load_settings is not None:
            self._apply_settings(self.load_settings())

    def _generate_button_click(self) -> None:
        """Validate inputs and generate a MIDI file from the selections."""
        key = self.key_var.get()
        selected_indices = self.chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror(
                "Input Error", "Please select at least one chord for the progression."
            )
            return
        # Build the chord progression from the selected listbox entries
        displays = [self.chord_listbox.get(i) for i in selected_indices]
        chord_progression = [self.display_map.get(d, d) for d in displays]
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
            if numerator <= 0 or denominator not in {1, 2, 4, 8, 16}:
                raise ValueError
        except ValueError:
            # Show one error message for any invalid numeric input
            messagebox.showerror(
                "Input Error",
                "Ensure BPM, Number of Notes, and Motif Length are integers and "
                "Time Signature is formatted as 'numerator/denominator' with "
                "denominator one of 1, 2, 4, 8 or 16.",
            )
            return

        if motif_length > notes_count:
            messagebox.showerror(
                "Input Error", "Motif length cannot exceed the number of notes."
            )
            return

        # Reject octave selections outside the safe MIDI range. The GUI slider
        # limits values to 1-7 but loading settings from disk may yield other
        # numbers.
        base_octave = self.base_octave_var.get()
        if base_octave < 0 or base_octave > 8:
            messagebox.showerror(
                "Input Error", "Base octave must be between 0 and 8."
            )
            return

        output_file = filedialog.asksaveasfilename(
            defaultextension=".mid", filetypes=[("MIDI files", "*.mid")]
        )
        if output_file:
            melody = self.generate_melody(
                key,
                notes_count,
                chord_progression,
                motif_length=motif_length,
                base_octave=base_octave,
            )
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
                chord_progression=(
                    chord_progression if self.include_chords_var.get() else None
                ),
                chords_separate=not self.chords_same_var.get(),
                program=INSTRUMENTS.get(self.instrument_var.get(), 0),
            )
            messagebox.showinfo("Success", f"MIDI file saved to {output_file}")
            if self.save_settings is not None and messagebox.askyesno(
                "Save Preferences", "Save these settings as defaults?"
            ):
                self.save_settings(self._collect_settings())

    def _preview_button_click(self) -> None:
        """Generate and play a melody preview then clean up.

        A temporary MIDI file is written and passed to the playback helper
        module. Regardless of whether playback succeeds or falls back to the
        system default player, the temporary file is removed afterward so it
        doesn't accumulate on disk.

        @returns None: The preview is played and temporary resources removed.
        """
        key = self.key_var.get()
        selected_indices = self.chord_listbox.curselection()
        if not selected_indices:
            messagebox.showerror(
                "Input Error", "Please select at least one chord for the progression."
            )
            return
        displays = [self.chord_listbox.get(i) for i in selected_indices]
        chords = [self.display_map.get(d, d) for d in displays]
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
            if numerator <= 0 or denominator not in {1, 2, 4, 8, 16}:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Input Error",
                "Ensure BPM, Number of Notes, and Motif Length are integers and "
                "Time Signature is formatted as 'numerator/denominator' with "
                "denominator one of 1, 2, 4, 8 or 16.",
            )
            return

        if motif_length > notes_count:
            messagebox.showerror(
                "Input Error", "Motif length cannot exceed the number of notes."
            )
            return

        melody = self.generate_melody(
            key,
            notes_count,
            chords,
            motif_length=motif_length,
            base_octave=self.base_octave_var.get(),
        )
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
            chord_progression=chords if self.include_chords_var.get() else None,
            chords_separate=not self.chords_same_var.get(),
            program=INSTRUMENTS.get(self.instrument_var.get(), 0),
        )
        playback_succeeded = False
        try:
            from . import playback

            try:
                playback.play_midi(tmp_path, soundfont=self.soundfont_var.get() or None)
                playback_succeeded = True
            except MidiPlaybackError:
                # Playback errors are expected when FluidSynth is missing or
                # fails to initialize. In that case fall back to the user's
                # default MIDI player so preview still works.
                self._open_default_player(tmp_path, delete_after=True)
        finally:
            if playback_succeeded:
                try:
                    os.remove(tmp_path)
                except OSError:
                    # Deletion failures aren't critical for preview playback and
                    # are ignored silently.
                    pass

    def _open_default_player(self, path: str, *, delete_after: bool = False) -> None:
        """Launch ``path`` in the user's default MIDI player.

        The player is executed in a daemon thread so the GUI stays responsive.
        When ``delete_after`` is ``True`` the file is removed after the player
        command exits. This is primarily used for temporary preview files.
        """

        def runner() -> None:
            try:
                player = os.environ.get("MELODY_PLAYER")
                if sys.platform.startswith("win"):
                    if player:
                        subprocess.run([player, path], check=False)
                    else:
                        subprocess.run(
                            [
                                "cmd",
                                "/c",
                                "start",
                                "/wait",
                                "",
                                path,
                            ],
                            check=False,
                        )
                elif sys.platform == "darwin":
                    if player:
                        subprocess.run(["open", "-W", "-a", player, path], check=False)
                    else:
                        subprocess.run(["open", "-W", path], check=False)
                else:
                    if player:
                        subprocess.run([player, path], check=False)
                    else:
                        subprocess.run(["xdg-open", path], check=False)
            except Exception as exc:  # pragma: no cover - platform dependent
                # Tkinter widgets must be updated from the main thread. Use
                # ``after`` to schedule the error dialog so it runs safely.
                self.root.after(
                    0,
                    messagebox.showerror,
                    "Preview Error",
                    f"Could not open MIDI file: {exc}",
                )
            finally:
                if delete_after:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        threading.Thread(target=runner, daemon=True).start()

    def _browse_soundfont(self) -> None:
        """Select a SoundFont ``.sf2`` file and store the path."""

        path = filedialog.askopenfilename(
            title="Choose SoundFont",
            filetypes=[("SoundFont", "*.sf2"), ("All files", "*")],
        )
        if path:
            self.soundfont_var.set(path)
        self._check_preview_available()

    def _randomize_chords(self) -> None:
        """Select a random chord progression and apply it to the list box.

        @returns None: List selection is updated with new chords.
        """
        if self.random_chords_fn is None:
            return
        progression = self.random_chords_fn(self.key_var.get(), 4)
        self.chord_listbox.selection_clear(0, tk.END)
        for chord in progression:
            if chord in self.sorted_chords:
                idx = self.sorted_chords.index(chord)
                self.chord_listbox.selection_set(idx)

    def _randomize_rhythm(self) -> None:
        """Create a random rhythm pattern and store it for generation.

        @returns None: Pattern stored in ``self.rhythm_pattern``.
        """
        if self.random_rhythm_fn is None:
            return
        # Store the newly generated pattern for use during MIDI export
        self.rhythm_pattern = self.random_rhythm_fn()

    def _load_preferences(self) -> None:
        """Reload settings from disk and apply them to the widgets.

        @returns None: Widgets reflect persisted values.
        """
        if self.load_settings is None:
            return
        self._apply_settings(self.load_settings())

    def run(self) -> None:
        """Start the Tk event loop to display the window.

        @returns None: This method blocks until the window closes.
        """
        # Hand control over to Tkinter so the application becomes interactive.
        # This call blocks until the window is closed.
        self.root.mainloop()

    def _collect_settings(self) -> Dict:
        """Gather current widget values into a dictionary.

        @returns Dict: Settings suitable for persistence.
        """
        # Persist any chords currently selected in the listbox
        chords = [self.chord_listbox.get(i) for i in self.chord_listbox.curselection()]
        return {
            "key": self.key_var.get(),
            "bpm": self.bpm_var.get(),
            "timesig": self.timesig_var.get(),
            "notes": self.notes_var.get(),
            "base_octave": self.base_octave_var.get(),
            "motif_length": int(self.motif_entry.get() or 0),
            "harmony": self.harmony_var.get(),
            "counterpoint": self.counterpoint_var.get(),
            "harmony_lines": int(self.harmony_lines.get() or 0),
            "chords": chords,
            "include_chords": self.include_chords_var.get(),
            "chords_same": self.chords_same_var.get(),
            "instrument": self.instrument_var.get(),
            "soundfont": self.soundfont_var.get(),
        }

    def _apply_settings(self, settings: Dict) -> None:
        """Set widget values based on ``settings`` dictionary.

        @param settings: Mapping of names to saved values.
        @returns None: Widgets are updated accordingly.
        """
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
        if "base_octave" in settings:
            self.base_octave_var.set(settings["base_octave"])
        if "motif_length" in settings:
            self.motif_entry.set(str(settings["motif_length"]))
        if "harmony" in settings:
            self.harmony_var.set(settings["harmony"])
        if "counterpoint" in settings:
            self.counterpoint_var.set(settings["counterpoint"])
        if "harmony_lines" in settings:
            self.harmony_lines.set(str(settings["harmony_lines"]))
        if "include_chords" in settings:
            self.include_chords_var.set(settings["include_chords"])
        if "chords_same" in settings:
            self.chords_same_var.set(settings["chords_same"])
        if "instrument" in settings and settings["instrument"] in INSTRUMENTS:
            self.instrument_var.set(settings["instrument"])
        if "soundfont" in settings:
            self.soundfont_var.set(settings["soundfont"])
            self._check_preview_available()
        self._update_chord_list()
        chords = settings.get("chords")
        if chords:
            self.chord_listbox.selection_clear(0, tk.END)
            for chord in chords:
                if chord in self.sorted_chords:
                    idx = self.sorted_chords.index(chord)
                    # Restore selection state for each saved chord
                    self.chord_listbox.selection_set(idx)
        # Refresh slider labels after applying new settings
        self._update_bpm_label(self.bpm_var.get())
        self._update_notes_label(self.notes_var.get())
        self._update_octave_label(self.base_octave_var.get())
