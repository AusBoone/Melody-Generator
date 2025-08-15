"""CLI validation tests for random chord progression handling.

These tests ensure ``run_cli`` rejects non-positive counts supplied to
``--random-chords`` and surfaces validation errors raised by the helper that
creates random progressions. Lightweight stubs for optional dependencies allow
the CLI to be imported without installing external libraries.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from pathlib import Path

import pytest


# --- Fixtures -----------------------------------------------------------------
@pytest.fixture()
def cli_env(monkeypatch) -> tuple[callable, types.ModuleType]:
    """Provide ``run_cli`` and package module with optional dependencies stubbed.

    Each test receives a fresh import of ``melody_generator`` with minimal
    stand-ins for external libraries. The stubs are removed afterwards so the
    wider test suite can import the real modules or define its own stubs.
    """

    # Create minimal 'mido' replacement used by the CLI when writing MIDI files.
    stub_mido = types.ModuleType("mido")

    class DummyMessage:
        """Simple MIDI message placeholder used by the test stubs."""

        def __init__(self, _type: str, **kw) -> None:
            self.type = _type
            self.time = kw.get("time", 0)
            self.note = kw.get("note")
            self.velocity = kw.get("velocity")
            self.program = kw.get("program")

    class DummyMidiFile:
        """Collects written MIDI tracks; avoids any disk I/O in tests."""

        last_instance = None

        def __init__(self, *args, **kwargs) -> None:
            self.tracks = []
            DummyMidiFile.last_instance = self

        def save(self, _path: str) -> None:  # pragma: no cover - file writing skipped
            pass

    class DummyMidiTrack(list):
        """List subclass used in place of ``mido.MidiTrack``."""

    stub_mido.Message = DummyMessage
    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = DummyMidiTrack
    stub_mido.MetaMessage = lambda *args, **kwargs: DummyMessage("meta", **kwargs)
    stub_mido.bpm2tempo = lambda bpm: bpm
    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    # Minimal ``tkinter`` replacement so GUI imports succeed during CLI tests.
    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    tk_stub.Tk = lambda: None
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))

    for name in ["melody_generator", "melody_generator.cli"]:
        sys.modules.pop(name, None)

    cli_module = importlib.import_module("melody_generator.cli")
    pkg = importlib.import_module("melody_generator")
    yield cli_module.run_cli, pkg

    for name in ["melody_generator", "melody_generator.cli"]:
        sys.modules.pop(name, None)


# --- Tests --------------------------------------------------------------------
@pytest.mark.parametrize("count", [0, -1])
def test_random_chords_rejects_non_positive(
    count: int, cli_env, monkeypatch, caplog
) -> None:
    """``run_cli`` should exit when ``--random-chords`` is zero or negative."""

    run_cli, _ = cli_env
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--key",
            "C",
            "--bpm",
            "120",
            "--timesig",
            "4/4",
            "--notes",
            "8",
            "--output",
            "out.mid",
            "--random-chords",
            str(count),
        ],
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc_info:
            run_cli()
    assert exc_info.value.code == 1
    assert "random chord count" in caplog.text.lower()


def test_random_chord_helper_error(cli_env, monkeypatch, caplog) -> None:
    """Surface ``ValueError`` raised by ``generate_random_chord_progression``."""

    run_cli, pkg = cli_env

    def bad_progression(_key: str, _count: int) -> list[str]:
        raise ValueError("invalid progression")

    monkeypatch.setattr(
        pkg, "generate_random_chord_progression", bad_progression
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--key",
            "C",
            "--bpm",
            "120",
            "--timesig",
            "4/4",
            "--notes",
            "8",
            "--output",
            "out.mid",
            "--random-chords",
            "2",
        ],
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc_info:
            run_cli()
    assert exc_info.value.code == 1
    assert "invalid progression" in caplog.text
