"""Ensure temporary preview file cleanup issues are logged.

This test exercises ``_preview_button_click`` when removing the temporary
preview MIDI file fails. A warning should be emitted while the preview
still counts as successful generation.
"""

import importlib
import logging
import sys
import types
from pathlib import Path

import pytest


def _prepare_gui_module(monkeypatch):
    """Import ``melody_generator.gui`` with lightweight stubs.

    The GUI depends on optional packages like ``mido`` and a full Tk
    environment. For testing we provide minimal stand-ins so the module
    can be imported without those heavy dependencies.
    """

    # ------------------------------------------------------------------
    # Stub out ``mido`` used by ``create_midi_file``.
    # ------------------------------------------------------------------
    stub_mido = types.ModuleType("mido")

    class DummyMidiFile:
        """Simplified MIDI container that writes placeholder data."""

        def __init__(self, *a, **k):
            self.tracks = []

        def save(self, path):
            Path(path).write_text("midi", encoding="utf-8")

    stub_mido.Message = lambda *a, **k: None
    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = lambda *a, **k: []
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    # ------------------------------------------------------------------
    # Provide a minimal ``playback`` module so preview playback succeeds.
    # ------------------------------------------------------------------
    playback_mod = types.ModuleType("melody_generator.playback")

    class MidiPlaybackError(RuntimeError):
        """Placeholder error type matching the real interface."""

    def play_midi(path, soundfont=None):
        """Pretend to play ``path`` successfully."""

    def open_default_player(path, delete_after=False):
        """Dummy fallback player used by the GUI."""

    playback_mod.MidiPlaybackError = MidiPlaybackError
    playback_mod.play_midi = play_midi
    playback_mod.open_default_player = open_default_player
    monkeypatch.setitem(sys.modules, "melody_generator.playback", playback_mod)

    # ------------------------------------------------------------------
    # Patch Tk to operate headlessly. ``_tkinter.create`` yields an interpreter
    # without needing a display server which keeps the test lightweight.
    # ------------------------------------------------------------------
    import tkinter as tk

    class DummyTk:
        """Minimal ``Tk`` replacement supporting required methods."""

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

    monkeypatch.setattr(tk, "Tk", DummyTk)

    # Silence dialogs during the test.
    tk.messagebox = types.SimpleNamespace(showerror=lambda *a, **k: None)
    tk.filedialog = types.SimpleNamespace()
    tk.ttk = types.SimpleNamespace()

    # Finally import the GUI module now that dependencies are stubbed.
    return importlib.import_module("melody_generator.gui")


class DummyVar:
    """Simple stand-in for ``tkinter`` variable classes."""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyListbox:
    """Minimal listbox returning a single chord selection."""

    def curselection(self):
        return (0,)

    def get(self, index):
        return "I: C"


@pytest.fixture
def gui(monkeypatch):
    """Yield a GUI instance configured with lightweight stubs."""

    gui_mod = _prepare_gui_module(monkeypatch)

    def minimal_build(self):
        self.key_var = DummyVar("C")
        self.chord_listbox = DummyListbox()
        self.display_map = {"I: C": "C"}
        self.bpm_var = DummyVar(120)
        self.notes_var = DummyVar(4)
        self.motif_entry = DummyVar("2")
        self.timesig_var = DummyVar("4/4")
        self.base_octave_var = DummyVar(4)
        self.instrument_var = DummyVar("Piano")
        self.harmony_lines = DummyVar("0")
        self.harmony_var = DummyVar(False)
        self.counterpoint_var = DummyVar(False)
        self.include_chords_var = DummyVar(False)
        self.chords_same_var = DummyVar(False)
        self.soundfont_var = DummyVar("")
        self.style_var = DummyVar("")
        self.ml_var = DummyVar(False)
        self.seed_var = DummyVar("")
        self.rhythm_pattern = None

    # Avoid real widget creation and theming.
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_setup_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_apply_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_check_preview_available", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_build_widgets", minimal_build)

    gui = gui_mod.MelodyGeneratorGUI(
        generate_melody=lambda *a, **k: ["C4", "E4", "G4"],
        create_midi_file=lambda melody, bpm, ts, path, **k: open(path, "w", encoding="utf-8").close(),
        scale={"C": ["C"]},
        chords={"C": ["C"]},
    )

    return gui_mod, gui


def test_preview_tempfile_cleanup_logged(gui, monkeypatch, caplog):
    """Failure to remove the temp file should emit a warning."""

    gui_mod, gui_obj = gui

    def raise_os_error(_path):
        raise OSError("permission denied")

    # Ensure cleanup fails.
    monkeypatch.setattr(gui_mod.os, "remove", raise_os_error)

    with caplog.at_level(logging.WARNING, logger="melody_generator.gui"):
        gui_obj._preview_button_click()

    assert "could not remove preview file" in caplog.text.lower()
