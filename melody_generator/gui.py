"""Tkinter front-end for melody generation.

The :class:`MelodyGeneratorGUI` class wraps the core library functions with a
minimal graphical interface that works on all platforms shipping Tkinter.  The
interface exposes the same options as the CLI—key selection, chord
progressions, tempo and so forth—while adding conveniences such as live
preview via FluidSynth and persistent user settings.

Only lightweight widgets are used so the application remains responsive even on
systems with modest resources.  All heavy lifting such as MIDI file creation or
counterpoint generation is delegated to :mod:`melody_generator`.
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
# * ``_generate_button_click`` now validates ``base_octave`` against
#   ``MIN_OCTAVE`` and ``MAX_OCTAVE`` so the register remains within the
#   MIDI specification.
# * ``_generate_button_click`` performs heavy work in a background thread,
#   displaying a progress bar and disabling inputs until completion so the
#   interface stays responsive.
# * ``__init__`` creates the Tk root before any ``BooleanVar`` or
#   ``StringVar`` objects to comply with Python 3.12's stricter Tkinter
#   initialization requirements.
# * Added a help button next to the style selector linking to
#   ``README_STYLE_WEIGHTS.md`` for preset vector documentation.
# * ``_setup_theme`` now logs a warning when the ``clam`` theme is
#   unavailable, providing visibility into fallback behavior.
# * Issued warnings when NumPy seeding fails so users understand that missing
#   the optional dependency limits deterministic behaviour.
# * Temporary preview files that cannot be deleted now log a warning, making
#   it clear that melody generation still succeeded even when cleanup fails.
# ---------------------------------------------------------------
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Tuple, Dict, Optional, Union
import logging
import os
import threading
from tempfile import NamedTemporaryFile
import random
import webbrowser
from pathlib import Path
from functools import partial

from . import diatonic_chords, MIN_OCTAVE, MAX_OCTAVE
from .sequence_model import load_sequence_model
from .style_embeddings import STYLE_VECTORS, get_style_vector

# ``MidiPlaybackError`` signals that preview playback failed within the
# ``playback`` helper module. Catching it allows the GUI to fall back to the
# system default player without masking unrelated errors.
from .playback import MidiPlaybackError, open_default_player

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


def _seed_rng(seed: int) -> None:
    """Seed Python and NumPy RNGs while logging failures.

    NumPy is optional for this project. When present, seeding its random
    generator alongside Python's ``random`` module ensures full reproducibility
    for features that leverage NumPy. If the import or seeding fails, a warning
    is emitted so users know that only Python's RNG was initialised, which may
    reduce determinism for NumPy-based operations.

    @param seed: Integer applied to available RNGs.
    @returns None: Logging captures any NumPy seeding issues.
    """

    random.seed(seed)
    try:  # pragma: no cover - NumPy may not be installed
        import numpy as _np

        _np.random.seed(seed)
    except Exception as exc:  # pragma: no cover - log import/seed failures
        logging.getLogger(__name__).warning(
            "NumPy seeding failed; deterministic behaviour may be limited: %s",
            exc,
        )


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

        # The Tk root must exist before creating any Tkinter variables.
        # Python 3.12 enforces this requirement whereas older versions
        # implicitly created a root.  By instantiating the window first and
        # explicitly passing it as ``master`` all ``BooleanVar`` and
        # ``StringVar`` objects are guaranteed a valid context.
        self.root = tk.Tk()
        self.root.title("Melody Generator")

        self.ml_var = tk.BooleanVar(master=self.root, value=False)
        self.humanize_var = tk.BooleanVar(master=self.root, value=True)
        self.style_var = tk.StringVar(master=self.root, value="")
        # Seed for deterministic generation. Empty string disables seeding.
        self.seed_var = tk.StringVar(master=self.root, value="")
        # Ornament placeholders can be toggled independently of the main melody
        # so arrangers only see the helper track when desired.
        self.ornament_var = tk.BooleanVar(master=self.root, value=False)
        self.styles = sorted(STYLE_VECTORS.keys())

        self._setup_theme()
        self._build_widgets()
        # Apply theme again so newly created widgets inherit colors
        self._apply_theme()
        self._check_preview_available()

    def _open_style_docs(self) -> None:
        """Open the style weight documentation in the default viewer.

        Clicking the help button next to the style selector opens the
        ``README_STYLE_WEIGHTS.md`` file so users can explore the
        available preset vectors and their musical implications.
        """

        docs = Path(__file__).resolve().parents[1] / "docs" / "README_STYLE_WEIGHTS.md"
        try:
            webbrowser.open(docs.as_uri())
        except Exception as exc:  # pragma: no cover - platform-specific failures
            messagebox.showerror("Documentation Error", f"Could not open {docs}: {exc}")

    def _setup_theme(self) -> None:
        """Configure ttk theme and basic colors.

        @returns None: Theme information is stored on the instance.
        """
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            # The platform may not ship with the ``clam`` theme. Instead of
            # failing silently, log a warning so developers know the default
            # theme will be used. ``warning`` keeps the GUI functional while
            # surfacing the issue for troubleshooting.
            logging.getLogger(__name__).warning(
                "Requested ttk theme 'clam' is unavailable; falling back to the default theme."
            )

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

    def _update_bpm_label(self, value: Union[str, int]) -> None:
        """Display the current BPM next to the slider.

        @param value: Slider value to display.
        @returns None: BPM label text is updated.
        """
        self.bpm_label.config(text=str(int(float(value))))

    def _update_notes_label(self, value: Union[str, int]) -> None:
        """Display the current number of notes next to the slider.

        @param value: Slider value to display.
        @returns None: Notes label text is updated.
        """
        self.notes_label.config(text=str(int(float(value))))

    def _update_octave_label(self, value: Union[str, int]) -> None:
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

        # ``self.inputs`` tracks interactive widgets that should be disabled
        # while long-running tasks execute. Keeping references simplifies
        # toggling their ``state`` en masse.
        self.inputs: List[tk.Widget] = []

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
        self.inputs.append(key_combobox)
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
        self.inputs.append(self.chord_listbox)

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
        self.inputs.append(bpm_scale)
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
        self.inputs.append(timesig_box)
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
        self.inputs.append(notes_scale)
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
        self.inputs.append(octave_scale)
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
        self.inputs.append(inst_box)

        # SoundFont selection path used by FluidSynth
        ttk.Label(frame, text="SoundFont:").grid(row=7, column=0, sticky="w")
        self.soundfont_var = tk.StringVar(value=os.environ.get("SOUND_FONT", ""))
        self.soundfont_entry = ttk.Entry(
            frame, textvariable=self.soundfont_var, width=25
        )
        self.soundfont_entry.grid(row=7, column=1)
        self.inputs.append(self.soundfont_entry)
        sf_button = ttk.Button(
            frame,
            text="Browse",
            command=self._browse_soundfont,
        )
        sf_button.grid(row=7, column=2, padx=(5, 0))
        self.inputs.append(sf_button)
        # Motif length entry
        ttk.Label(frame, text="Motif Length:").grid(row=8, column=0, sticky="w")
        self.motif_entry = ttk.Spinbox(frame, from_=1, to=32, width=5)
        self.motif_entry.grid(row=8, column=1)
        self.inputs.append(self.motif_entry)
        self._create_tooltip(self.motif_entry, "Length of repeating motif")
        self.motif_entry.set(4)
        ttk.Label(frame, text="Seed:").grid(row=8, column=2, sticky="w")
        seed_entry = ttk.Entry(frame, textvariable=self.seed_var, width=6)
        seed_entry.grid(row=8, column=3)
        self.inputs.append(seed_entry)

        ml_check = ttk.Checkbutton(
            frame,
            text="Use ML Model",
            variable=self.ml_var,
        )
        ml_check.grid(row=9, column=0, columnspan=2)
        self.inputs.append(ml_check)

        ttk.Label(frame, text="Style:").grid(row=9, column=2, sticky="w")
        self.style_combo = ttk.Combobox(
            frame,
            textvariable=self.style_var,
            values=self.styles,
            state="readonly",
        )
        self.style_combo.grid(row=9, column=3)
        self.inputs.append(self.style_combo)
        self._create_tooltip(self.style_combo, "Select a preset style vector; click ? for descriptions")
        style_help = ttk.Button(
            frame,
            text="?",
            width=2,
            command=self._open_style_docs,
        )
        style_help.grid(row=9, column=4, padx=(5, 0))
        self.inputs.append(style_help)


        # Harmony checkbox
        self.harmony_var = tk.BooleanVar(value=False)
        harmony_check = ttk.Checkbutton(
            frame,
            text="Add Harmony",
            variable=self.harmony_var,
        )
        harmony_check.grid(row=10, column=0, columnspan=2)
        self.inputs.append(harmony_check)

        self.counterpoint_var = tk.BooleanVar(value=False)
        counterpoint_check = ttk.Checkbutton(
            frame,
            text="Add Counterpoint",
            variable=self.counterpoint_var,
        )
        counterpoint_check.grid(row=11, column=0, columnspan=2)
        self.inputs.append(counterpoint_check)

        ttk.Label(frame, text="Harmony Lines:").grid(row=12, column=0, sticky="w")
        self.harmony_lines = ttk.Spinbox(frame, from_=0, to=4, width=5)
        self.harmony_lines.set(0)
        self.harmony_lines.grid(row=12, column=1)
        self.inputs.append(self.harmony_lines)

        self.include_chords_var = tk.BooleanVar(value=False)
        include_chords_check = ttk.Checkbutton(
            frame,
            text="Include Chords",
            variable=self.include_chords_var,
        )
        include_chords_check.grid(row=13, column=0, columnspan=2)
        self.inputs.append(include_chords_check)

        ornament_check = ttk.Checkbutton(
            frame,
            text="Ornament Placeholders",
            variable=self.ornament_var,
        )
        ornament_check.grid(row=14, column=0, columnspan=2)
        self.inputs.append(ornament_check)

        self.chords_same_var = tk.BooleanVar(value=False)
        merge_chords_check = ttk.Checkbutton(
            frame,
            text="Merge Chords With Melody",
            variable=self.chords_same_var,
        )
        merge_chords_check.grid(row=15, column=0, columnspan=2)
        self.inputs.append(merge_chords_check)

        humanize_check = ttk.Checkbutton(
            frame,
            text="Humanize Performance",
            variable=self.humanize_var,
        )
        humanize_check.grid(row=16, column=0, columnspan=2)
        self.inputs.append(humanize_check)

        # Randomize buttons
        rand_chords_btn = ttk.Button(
            frame,
            text="Randomize Chords",
            command=self._randomize_chords,
        )
        rand_chords_btn.grid(row=17, column=0, columnspan=2, pady=(5, 0))
        self.inputs.append(rand_chords_btn)
        rand_rhythm_btn = ttk.Button(
            frame,
            text="Randomize Rhythm",
            command=self._randomize_rhythm,
        )
        rand_rhythm_btn.grid(row=18, column=0, columnspan=2, pady=(5, 0))
        self.inputs.append(rand_rhythm_btn)

        load_prefs_btn = ttk.Button(
            frame,
            text="Load Preferences",
            command=self._load_preferences,
        )
        load_prefs_btn.grid(row=19, column=0, columnspan=2, pady=(5, 0))
        self.inputs.append(load_prefs_btn)

        preview_btn = ttk.Button(
            frame,
            text="Preview Melody",
            command=self._preview_button_click,
        )
        preview_btn.grid(row=20, column=0, columnspan=2, pady=(5, 0))
        self.inputs.append(preview_btn)
        self.preview_notice = ttk.Label(
            frame,
            text="",
            foreground="yellow",
        )
        self.preview_notice.grid(row=20, column=2, sticky="w")

        # Generate button
        generate_btn = ttk.Button(
            frame,
            text="Generate Melody",
            command=self._generate_button_click,
        )
        generate_btn.grid(row=21, column=0, columnspan=2, pady=10)
        self.inputs.append(generate_btn)

        self.theme_var = tk.BooleanVar(value=self.dark_mode)
        theme_toggle = ttk.Checkbutton(
            frame,
            text="Toggle Dark Mode",
            command=self._toggle_theme,
            variable=self.theme_var,
        )
        theme_toggle.grid(row=21, column=0, columnspan=2, pady=(5, 0))
        self.inputs.append(theme_toggle)

        # Progress bar shown while generation runs. Hidden by default.
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=22, column=0, columnspan=5, pady=(5, 0))
        self.progress.grid_remove()

        # Apply persisted settings if available
        if self.load_settings is not None:
            self._apply_settings(self.load_settings())

    def _set_inputs_state(self, state: str) -> None:
        """Set ``state`` on all interactive widgets.

        Disabling widgets prevents user interaction while background tasks
        execute, avoiding race conditions or accidental re-entry.

        @param state: Tkinter widget state such as ``"disabled"`` or
            ``"normal"``.
        @returns None: All known input widgets are updated best effort.
        """

        for widget in self.inputs:
            try:
                widget.configure(state=state)
            except tk.TclError:
                # Not every widget type supports a ``state`` option; those are
                # safely ignored.
                continue

    def _generate_button_click(self) -> None:
        """Validate inputs and start background MIDI generation."""

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
        if not MIN_OCTAVE <= base_octave <= MAX_OCTAVE:
            messagebox.showerror(
                "Input Error",
                f"Base octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}.",
            )
            return

        output_file = filedialog.asksaveasfilename(
            defaultextension=".mid", filetypes=[("MIDI files", "*.mid")]
        )
        if not output_file:
            return

        style_name = self.style_var.get() or None
        if style_name:
            try:
                get_style_vector(style_name)
            except KeyError:
                messagebox.showerror("Input Error", f"Unknown style: {style_name}")
                return

        seq_model = None
        if self.ml_var.get():
            try:
                seq_model = load_sequence_model(None, len(self.scale[key]))
            except RuntimeError as exc:
                messagebox.showerror("Dependency Error", str(exc))
                return

        seed_val = self.seed_var.get()
        if seed_val:
            try:
                seed = int(seed_val)
                # Seed Python and, when installed, NumPy to provide fully
                # deterministic output. Any failure to seed NumPy is logged so
                # users know why reproducibility might be incomplete.
                _seed_rng(seed)
            except ValueError:
                messagebox.showerror("Input Error", "Seed must be an integer")
                return

        try:
            lines = int(self.harmony_lines.get() or 0)
        except ValueError:
            lines = 0

        params = {
            "key": key,
            "notes_count": notes_count,
            "chord_progression": chord_progression,
            "motif_length": motif_length,
            "base_octave": base_octave,
            "bpm": bpm,
            "timesig": (numerator, denominator),
            "output_file": output_file,
            "style_name": style_name,
            "seq_model": seq_model,
            "harmony_lines": lines,
            "add_counterpoint": self.counterpoint_var.get(),
            "harmony": self.harmony_var.get(),
            "include_chords": self.include_chords_var.get(),
            "chords_same": self.chords_same_var.get(),
            "program": INSTRUMENTS.get(self.instrument_var.get(), 0),
            "humanize": self.humanize_var.get() if hasattr(self, "humanize_var") else True,
            "rhythm_pattern": self.rhythm_pattern,
            "ornaments": self.ornament_var.get(),
        }

        # Disable controls and show progress indicator while the worker runs.
        self._set_inputs_state("disabled")
        self.progress.grid()
        self.progress.start()
        threading.Thread(target=self._generate_worker, args=(params,), daemon=True).start()

    def _generate_worker(self, params: Dict) -> None:
        """Perform melody generation and MIDI export in a background thread.

        All Tk interactions are postponed to the main thread via
        ``root.after`` to respect Tkinter's thread-safety constraints.

        @param params: Pre-validated options collected from the GUI.
        @returns None: Completion is signaled through ``_generation_complete``.
        """

        try:
            melody = self.generate_melody(
                params["key"],
                params["notes_count"],
                params["chord_progression"],
                motif_length=params["motif_length"],
                base_octave=params["base_octave"],
                sequence_model=params["seq_model"],
                style=params["style_name"],
            )
            extra: List[List[str]] = []
            if self.harmony_line_fn is not None:
                for _ in range(max(0, params["harmony_lines"])):
                    extra.append(self.harmony_line_fn(melody))
            if self.counterpoint_fn is not None and params["add_counterpoint"]:
                extra.append(self.counterpoint_fn(melody, params["key"]))
            self.create_midi_file(
                melody,
                params["bpm"],
                params["timesig"],
                params["output_file"],
                harmony=params["harmony"],
                pattern=params["rhythm_pattern"],
                extra_tracks=extra,
                chord_progression=(
                    params["chord_progression"] if params["include_chords"] else None
                ),
                chords_separate=not params["chords_same"],
                program=params["program"],
                humanize=params["humanize"],
                ornaments=params["ornaments"],
            )
        except Exception as exc:  # pragma: no cover - rare failures
            # Use ``functools.partial`` to bind ``exc`` for the callback executed
            # on the main thread, preventing linter warnings about an unused
            # variable while still surfacing the original exception.
            self.root.after(0, partial(self._generation_complete, error=exc))
        else:
            self.root.after(
                0,
                lambda: self._generation_complete(output_file=params["output_file"]),
            )

    def _generation_complete(
        self, *, output_file: Optional[str] = None, error: Optional[Exception] = None
    ) -> None:
        """Re-enable widgets and report generation result.

        This callback executes on the main GUI thread.

        @param output_file: Path to the saved MIDI file when successful.
        @param error: Exception raised by the worker, if any.
        @returns None: Widgets are restored and dialogs displayed.
        """

        self.progress.stop()
        self.progress.grid_remove()
        self._set_inputs_state("normal")
        if error is not None:
            messagebox.showerror("Generation Error", str(error))
            return
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

        style_name = self.style_var.get() or None
        if style_name:
            try:
                get_style_vector(style_name)
            except KeyError:
                messagebox.showerror("Input Error", f"Unknown style: {style_name}")
                return

        seq_model = None
        if self.ml_var.get():
            try:
                seq_model = load_sequence_model(None, len(self.scale[key]))
            except RuntimeError as exc:
                messagebox.showerror("Dependency Error", str(exc))
                return

        seed_val = self.seed_var.get()
        if seed_val:
            try:
                seed = int(seed_val)
                # Mirror CLI behaviour: seed both RNGs and warn when NumPy is
                # unavailable so preview results remain transparent to users.
                _seed_rng(seed)
            except ValueError:
                messagebox.showerror("Input Error", "Seed must be an integer")
                return

        melody = self.generate_melody(
            key,
            notes_count,
            chords,
            motif_length=motif_length,
            base_octave=self.base_octave_var.get(),
            sequence_model=seq_model,
            style=style_name,
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
            humanize=self.humanize_var.get()
            if hasattr(self, "humanize_var")
            else True,
            ornaments=self.ornament_var.get(),
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
                except OSError as exc:
                    # Log cleanup issues without interrupting the user. Even if
                    # the temporary file remains, melody generation succeeded so
                    # the leftover file can be removed manually later.
                    logging.getLogger(__name__).warning(
                        "Could not remove preview file %s; generation succeeded: %s",
                        tmp_path,
                        exc,
                    )

    def _open_default_player(self, path: str, *, delete_after: bool = False) -> None:
        """Launch ``path`` in the user's default MIDI player.

        The player is executed in a daemon thread so the GUI stays responsive.
        When ``delete_after`` is ``True`` the file is removed after the player
        command exits. This is primarily used for temporary preview files.
        """

        def runner() -> None:
            try:
                open_default_player(path, delete_after=delete_after)
            except Exception as exc:  # pragma: no cover - platform dependent
                # Tkinter widgets must be updated from the main thread. Use
                # ``after`` to schedule the error dialog so it runs safely.
                self.root.after(
                    0,
                    messagebox.showerror,
                    "Preview Error",
                    f"Could not open MIDI file: {exc}",
                )
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
            "ornaments": self.ornament_var.get(),
            "chords_same": self.chords_same_var.get(),
            "instrument": self.instrument_var.get(),
            "soundfont": self.soundfont_var.get(),
            "humanize": self.humanize_var.get(),
            "seed": self.seed_var.get(),
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
        if "ornaments" in settings:
            self.ornament_var.set(settings["ornaments"])
        if "chords_same" in settings:
            self.chords_same_var.set(settings["chords_same"])
        if "humanize" in settings:
            self.humanize_var.set(settings["humanize"])
        if "instrument" in settings and settings["instrument"] in INSTRUMENTS:
            self.instrument_var.set(settings["instrument"])
        if "soundfont" in settings:
            self.soundfont_var.set(settings["soundfont"])
            self._check_preview_available()
        if "seed" in settings:
            self.seed_var.set(str(settings["seed"]))
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
