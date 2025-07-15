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
