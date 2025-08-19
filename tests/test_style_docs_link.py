"""Ensure style weight documentation is discoverable from interfaces."""

import importlib
import sys
from pathlib import Path
import tkinter as tk
import pytest


def test_cli_help_mentions_style_docs(capsys):
    """Running the CLI with --help should mention the style weight README.

    The argument description guides users to the preset vectors so they can
    understand how style values affect melody generation.
    """
    mod = importlib.import_module("melody_generator.cli")
    old = sys.argv
    sys.argv = ["prog", "--help"]
    with pytest.raises(SystemExit):
        mod.run_cli()
    out = capsys.readouterr().out
    sys.argv = old
    assert "README_STYLE_WEIGHTS.md" in out


def test_gui_open_style_docs(monkeypatch):
    """Clicking the GUI help button should open the style documentation.

    The method constructs a file URI to the README and dispatches it to
    ``webbrowser.open``. The test intercepts the call to confirm the correct
    path is used without launching an external application.
    """
    gui_mod = importlib.import_module("melody_generator.gui")

    class DummyTk:
        """Minimal stand-in for ``tkinter.Tk`` to run headless."""

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

    monkeypatch.setattr(gui_mod.tk, "Tk", DummyTk)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_setup_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_build_widgets", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_apply_theme", lambda self: None)
    monkeypatch.setattr(gui_mod.MelodyGeneratorGUI, "_check_preview_available", lambda self: None)

    opened = {}

    def fake_open(uri):
        opened["uri"] = uri
        return True

    monkeypatch.setattr(gui_mod.webbrowser, "open", fake_open)

    gui = gui_mod.MelodyGeneratorGUI(
        generate_melody=lambda *a, **k: [],
        create_midi_file=lambda *a, **k: None,
        scale={"C": ["C"]},
        chords={"C": ["C"]},
    )
    gui._open_style_docs()

    expected = (Path(gui_mod.__file__).resolve().parents[1] / "docs" / "README_STYLE_WEIGHTS.md").as_uri()
    assert opened["uri"] == expected
