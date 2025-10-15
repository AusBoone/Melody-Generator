"""Regression tests for the desktop GUI initialization order.

The GUI used to create ``BooleanVar`` and ``StringVar`` instances before the
Tk root existed, which raises ``RuntimeError`` on Python 3.12. These tests
patch ``tkinter`` so the initialization can run headless and verify that
the variables share the newly created root.
"""

import importlib
import sys
import types
from pathlib import Path
import tkinter as tk

# Ensure the repository root is on ``sys.path`` so the package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_gui_init_root_before_vars(monkeypatch):
    """The root window must be created prior to Tk variables."""
    # Stub ``mido`` so the module can be imported without the real dependency.
    stub_mido = types.ModuleType("mido")
    stub_mido.Message = lambda *a, **k: None

    class DummyMidiFile:
        def __init__(self, *a, **k):
            self.tracks = []

        def save(self, _path):
            pass

    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = lambda *a, **k: []
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    gui_mod = importlib.import_module("melody_generator.gui")

    class DummyTk:
        """Minimal stand-in for ``tkinter.Tk`` that works without a display."""

        def __init__(self, *args, **kwargs):
            # ``_tkinter.create`` with ``wantTk=False`` provides a Tcl interpreter
            # without requiring any windowing system.
            import _tkinter

            self.tk = _tkinter.create(
                None, "py", "Tk", False, False, False, False, None
            )
            self.master = None
            self._w = "."
            tk._default_root = self

        def _root(self):
            return self

        def __call__(self, *args):
            return self.tk.call(*args)

        def title(self, *args, **kwargs):
            pass

        def option_add(self, *args, **kwargs):
            pass

        def configure(self, *args, **kwargs):
            pass

    monkeypatch.setattr(gui_mod.tk, "Tk", DummyTk)

    # Skip widget creation to keep the test lightweight.
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_setup_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_build_widgets", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_apply_theme", lambda self: None)
    monkeypatch.setattr(
        gui_mod.MelodyGeneratorGUI, "_check_preview_available", lambda self: None
    )

    gui = gui_mod.MelodyGeneratorGUI(
        generate_melody=lambda *a, **k: [],
        create_midi_file=lambda *a, **k: None,
        scale={"C": ["C"]},
        chords={"C": ["C"]},
    )

    # ``Variable`` instances store the root object in ``_root``. The ``str``
    # representation of this object is ``"."`` but identity should match the
    # ``DummyTk`` instance created above.
    assert gui.ml_var._root is gui.root
    assert gui.humanize_var._root is gui.root
    assert gui.style_var._root is gui.root
    assert gui.seed_var._root is gui.root


def test_generate_runs_in_worker_thread(monkeypatch):
    """Generation occurs off the main thread and widgets recover state."""

    # Provide a stub ``mido`` module so the GUI can be imported.
    stub_mido = types.ModuleType("mido")
    stub_mido.Message = lambda *a, **k: None

    class DummyMidiFile:
        def __init__(self, *a, **k):
            self.tracks = []

        def save(self, _path):
            pass

    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = lambda *a, **k: []
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    gui_mod = importlib.import_module("melody_generator.gui")

    class DummyTk:
        """Simplified ``Tk`` replacement with immediate ``after`` callbacks."""

        def __init__(self, *args, **kwargs):
            import _tkinter

            self.tk = _tkinter.create(None, "py", "Tk", False, False, False, False, None)
            self.master = None
            self._w = "."
            tk._default_root = self

        def _root(self):
            return self

        def __call__(self, *args):
            return self.tk.call(*args)

        def title(self, *args, **kwargs):
            pass

        def option_add(self, *args, **kwargs):
            pass

        def configure(self, *args, **kwargs):
            pass

        def after(self, _delay, func, *args):
            func(*args)

    monkeypatch.setattr(gui_mod.tk, "Tk", DummyTk)

    class DummyVar:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class DummyListbox:
        def __init__(self):
            self.state = "normal"

        def curselection(self):
            return (0,)

        def get(self, _index):
            return "I: C"

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.state = kwargs["state"]

    class DummyProgressbar:
        def __init__(self):
            self.running = False
            self.visible = False

        def grid(self, *a, **k):
            self.visible = True

        def grid_remove(self):
            self.visible = False

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

    def minimal_build(self):
        self.key_var = DummyVar("C")
        self.chord_listbox = DummyListbox()
        self.display_map = {"I: C": "C"}
        self.bpm_var = DummyVar(120)
        self.notes_var = DummyVar(16)
        self.motif_entry = DummyVar("4")
        self.timesig_var = DummyVar("4/4")
        self.base_octave_var = DummyVar(4)
        self.instrument_var = DummyVar("Piano")
        self.harmony_lines = DummyVar("0")
        self.harmony_var = DummyVar(False)
        self.counterpoint_var = DummyVar(False)
        self.include_chords_var = DummyVar(False)
        self.chords_same_var = DummyVar(False)
        self.ornament_var = DummyVar(False)
        self.progress = DummyProgressbar()
        self.inputs = [self.chord_listbox]
        self.rhythm_pattern = None

    # Bypass real widget creation and theming.
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_setup_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_apply_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_check_preview_available", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_build_widgets", minimal_build)

    # Prevent dialogs from blocking the test.
    # ``tkinter.filedialog`` may lack ``asksaveasfilename`` in the stub module,
    # so allow creation of the attribute during monkeypatching.
    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: "out.mid",
        raising=False,
    )
    monkeypatch.setattr(
        gui_mod.messagebox, "showinfo", lambda *a, **k: None, raising=False
    )
    monkeypatch.setattr(
        gui_mod.messagebox, "askyesno", lambda *a, **k: False, raising=False
    )
    monkeypatch.setattr(
        gui_mod.messagebox, "showerror", lambda *a, **k: None, raising=False
    )

    thread_calls = {}

    class DummyThread:
        def __init__(self, target, args=(), daemon=None):
            thread_calls["daemon"] = daemon
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(gui_mod.threading, "Thread", DummyThread)

    gui = gui_mod.MelodyGeneratorGUI(
        generate_melody=lambda *a, **k: [],
        create_midi_file=lambda *a, **k: None,
        scale={"C": ["C"]},
        chords={"C": ["C"]},
    )

    # Replace generation functions to observe widget state during execution.
    states = {}

    def gen_fn(*a, **k):
        states["generate"] = gui.chord_listbox.state
        return []

    def create_fn(*a, **k):
        states["create"] = gui.chord_listbox.state

    gui.generate_melody = gen_fn
    gui.create_midi_file = create_fn

    gui._generate_button_click()

    assert states["generate"] == "disabled"
    assert states["create"] == "disabled"
    assert gui.chord_listbox.state == "normal"
    assert gui.progress.running is False
    assert thread_calls["daemon"] is True
