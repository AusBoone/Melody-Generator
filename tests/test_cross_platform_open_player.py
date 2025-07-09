"""Cross-platform tests for the default MIDI player helper.

This module ensures ``open_default_player`` constructs the correct
``subprocess`` command on Windows, macOS and Linux. The helper must
include ``--wait`` on Linux so temporary preview files remain until the
external player exits. Each test also verifies files are removed when
``delete_after`` is ``True``.
"""

import importlib
import sys
import types
from pathlib import Path

import pytest

# Ensure the repository root is on ``sys.path`` so ``melody_generator`` can be
# imported regardless of where pytest is executed from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize(
    "platform,expected_prefix",
    [
        ("win32", ["cmd", "/c", "start", "/wait", ""]),
        ("darwin", ["open", "-W"]),
        ("linux", ["xdg-open", "--wait"]),
    ],
)
def test_open_player_platform_commands(monkeypatch, tmp_path, platform, expected_prefix):
    """``open_default_player`` should issue platform specific commands.

    The ``subprocess.run`` call must begin with ``expected_prefix`` and include
    the target MIDI file path. When ``delete_after`` is enabled the file should
    be removed after playback completes.
    """

    # Provide minimal stubs so ``melody_generator`` imports without extras.
    mido_stub = types.ModuleType("mido")
    mido_stub.Message = object
    mido_stub.MidiFile = object
    mido_stub.MidiTrack = object
    mido_stub.bpm2tempo = lambda bpm: bpm
    mido_stub.MetaMessage = object
    monkeypatch.setitem(sys.modules, "mido", mido_stub)

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    # Import playback after stubbing optional modules so import succeeds.
    playback = importlib.import_module("melody_generator.playback")
    open_default_player = playback.open_default_player

    midi = tmp_path / "example.mid"
    midi.write_text("data")

    calls = []

    def fake_run(cmd, check=False):
        """Record invocations of ``subprocess.run`` for assertions."""
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(playback.subprocess, "run", fake_run)
    monkeypatch.setattr(playback.os, "environ", {})
    monkeypatch.setattr(playback.sys, "platform", platform, raising=False)

    open_default_player(str(midi), delete_after=True)

    assert calls, "subprocess.run was not called"
    assert calls[0] == expected_prefix + [str(midi)]
    assert not midi.exists()


def test_custom_player_with_spaces(monkeypatch, tmp_path):
    """Custom ``MELODY_PLAYER`` containing spaces should be parsed correctly."""

    mido_stub = types.ModuleType("mido")
    mido_stub.Message = object
    mido_stub.MidiFile = object
    mido_stub.MidiTrack = object
    mido_stub.bpm2tempo = lambda bpm: bpm
    mido_stub.MetaMessage = object
    monkeypatch.setitem(sys.modules, "mido", mido_stub)

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    playback = importlib.import_module("melody_generator.playback")
    open_default_player = playback.open_default_player

    midi = tmp_path / "example.mid"
    midi.write_text("data")

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(playback.subprocess, "run", fake_run)
    monkeypatch.setattr(
        playback.os,
        "environ",
        {"MELODY_PLAYER": "/usr/bin/custom player"},
    )
    monkeypatch.setattr(playback.sys, "platform", "linux", raising=False)

    open_default_player(str(midi), delete_after=True)

    assert calls == [["/usr/bin/custom", "player", str(midi)]]
    assert not midi.exists()


def test_open_default_player_missing_file(monkeypatch):
    """A nonexistent MIDI file should raise ``FileNotFoundError``."""

    mido_stub = types.ModuleType("mido")
    mido_stub.Message = object
    mido_stub.MidiFile = object
    mido_stub.MidiTrack = object
    mido_stub.bpm2tempo = lambda bpm: bpm
    mido_stub.MetaMessage = object
    monkeypatch.setitem(sys.modules, "mido", mido_stub)

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    playback = importlib.import_module("melody_generator.playback")
    open_default_player = playback.open_default_player

    monkeypatch.setattr(playback.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(playback.os, "environ", {})
    monkeypatch.setattr(playback.sys, "platform", "linux", raising=False)

    with pytest.raises(FileNotFoundError):
        open_default_player("nope.mid")
