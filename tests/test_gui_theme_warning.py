"""Tests for theme configuration warnings in :mod:`melody_generator.gui`.

These regression tests ensure that the GUI provides visibility when the
preferred ttk theme is unavailable. The GUI should warn but still continue
with the default theme so the interface remains functional.
"""

import importlib
import sys
import types
from pathlib import Path
import tkinter as tk
import tkinter.ttk as ttk_mod


def _stub_mido():
    """Install a lightweight stub of :mod:`mido` for GUI imports.

    The real ``mido`` dependency is not required for these tests and may not be
    installed. Providing a minimal stub allows :mod:`melody_generator.gui` to be
    imported without pulling in the actual library.
    """

    stub_mido = types.ModuleType("mido")
    stub_mido.Message = lambda *a, **k: None

    class DummyMidiFile:
        """Minimal ``MidiFile`` placeholder used by the GUI."""

        def __init__(self, *a, **k):
            self.tracks = []

        def save(self, _path):
            """Pretend to write a file to disk."""

            return None

    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = lambda *a, **k: []
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    sys.modules["mido"] = stub_mido


def test_setup_theme_warns_when_clam_missing(monkeypatch, caplog):
    """A warning is logged if the desired ttk theme is absent.

    The GUI requests the ``clam`` theme, which may not exist on minimal Tk
    builds. The application should log a warning and gracefully continue with
    the default theme, enabling the interface to remain usable.
    """

    _stub_mido()

    # Ensure the repository root is importable so ``melody_generator`` resolves.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    class DummyStyle:
        """Style object whose ``theme_use`` raises ``TclError``."""

        def __init__(self, _root):
            return None

        def theme_use(self, _theme):
            raise tk.TclError("no theme")

    # Patch the global ``tkinter.ttk.Style`` before importing the GUI so it
    # raises ``TclError`` whenever the application selects a theme.
    monkeypatch.setattr(ttk_mod, "Style", DummyStyle)

    gui_mod = importlib.import_module("melody_generator.gui")

    class DummyTk:
        """Simplified ``Tk`` replacement usable without a display server."""

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
            return None

        def option_add(self, *args, **kwargs):
            return None

        def configure(self, *args, **kwargs):
            return None

    monkeypatch.setattr(gui_mod.tk, "Tk", DummyTk)

    # Skip widget construction and subsequent theme application for speed.
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_build_widgets", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_apply_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_check_preview_available", lambda self: None)

    caplog.set_level("WARNING")

    gui_mod.MelodyGeneratorGUI(
        generate_melody=lambda *a, **k: [],
        create_midi_file=lambda *a, **k: None,
        scale={"C": ["C"]},
        chords={"C": ["C"]},
    )

    # Ensure a warning mentioning the missing theme was emitted.
    assert any("clam" in record.message for record in caplog.records)
