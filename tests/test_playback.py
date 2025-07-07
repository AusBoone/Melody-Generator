"""Tests for the playback helper functions.

This module focuses on verifying the behavior of ``_resolve_soundfont`` and
``render_midi_to_wav``. The first must honour the ``SOUND_FONT`` environment
variable and report missing files via ``MidiPlaybackError``. The latter should
invoke ``subprocess.run`` with the correct command when rendering audio.
"""

import subprocess
import sys
import types
from pathlib import Path

import importlib

import pytest

# Ensure the repository root is on `sys.path` so `melody_generator` can be imported regardless of where pytest is executed from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Import the playback module freshly each time so environment changes are seen.
# Provide lightweight stand-ins for optional dependencies so the package can be
# imported without installing them.
mido_stub = types.ModuleType("mido")
mido_stub.Message = object
mido_stub.MidiFile = object
mido_stub.MidiTrack = object
mido_stub.bpm2tempo = lambda bpm: bpm
mido_stub.MetaMessage = object
sys.modules.setdefault("mido", mido_stub)

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

playback = importlib.import_module("melody_generator.playback")
_resolve_soundfont = playback._resolve_soundfont
render_midi_to_wav = playback.render_midi_to_wav
MidiPlaybackError = playback.MidiPlaybackError
open_default_player = playback.open_default_player


def test_resolve_soundfont_env_variable(tmp_path, monkeypatch):
    """Environment variable ``SOUND_FONT`` overrides other locations.

    When ``SOUND_FONT`` points at an existing file it should be returned
    unchanged by ``_resolve_soundfont``. This ensures users can configure the
    SoundFont path without passing it explicitly.
    """
    sf = tmp_path / "custom.sf2"
    sf.write_text("soundfont")
    monkeypatch.setenv("SOUND_FONT", str(sf))

    result = _resolve_soundfont(None)

    assert Path(result) == sf


def test_resolve_soundfont_expands_user(tmp_path, monkeypatch):
    """``_resolve_soundfont`` should expand ``~`` in paths."""

    home = tmp_path / "home"
    home.mkdir()
    sf = home / "font.sf2"
    sf.write_text("soundfont")
    monkeypatch.setenv("HOME", str(home))

    result = _resolve_soundfont("~/font.sf2")

    assert Path(result) == sf


def test_resolve_soundfont_missing_file(monkeypatch):
    """Missing SoundFonts raise ``MidiPlaybackError``.

    ``_resolve_soundfont`` should fail early with a clear error when the path
    provided via ``SOUND_FONT`` does not exist.
    """
    monkeypatch.setenv("SOUND_FONT", "/non/existent/path.sf2")

    with pytest.raises(MidiPlaybackError):
        _resolve_soundfont(None)


def test_render_midi_invokes_subprocess(tmp_path, monkeypatch):
    """``render_midi_to_wav`` runs ``fluidsynth`` with expected arguments."""
    midi = tmp_path / "in.mid"
    wav = tmp_path / "out.wav"
    midi.write_text("midi")
    wav.write_text("")

    called = {}

    def fake_run(cmd, check=False, stdout=None, stderr=None):
        """Record ``subprocess.run`` arguments for assertion."""
        called["cmd"] = cmd
        called["check"] = check
        called["stdout"] = stdout
        called["stderr"] = stderr

    monkeypatch.setattr(playback, "_resolve_soundfont", lambda sf: str(tmp_path / "font.sf2"))
    monkeypatch.setattr(subprocess, "run", fake_run)

    render_midi_to_wav(str(midi), str(wav))

    assert called["cmd"] == [
        "fluidsynth",
        "-ni",
        "-F",
        str(wav),
        str(tmp_path / "font.sf2"),
        str(midi),
    ]
    assert called["check"] is True
    assert called["stdout"] == subprocess.DEVNULL
    assert called["stderr"] == subprocess.DEVNULL


@pytest.mark.parametrize(
    "platform,expected_prefix",
    [
        ("win32", ["cmd", "/c", "start", "/wait", ""]),
        ("darwin", ["open", "-W"]),
        ("linux", ["xdg-open", "--wait"]),
    ],
)
def test_open_default_player_commands(monkeypatch, tmp_path, platform, expected_prefix):
    """Verify platform-specific commands used by ``open_default_player``."""

    midi = tmp_path / "x.mid"
    midi.write_text("data")

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(playback.subprocess, "run", fake_run)
    monkeypatch.setattr(playback.os, "environ", {})
    monkeypatch.setattr(playback.sys, "platform", platform, raising=False)

    open_default_player(str(midi), delete_after=True)

    assert calls
    assert calls[0][: len(expected_prefix)] == expected_prefix
    assert calls[0][-1] == str(midi)
    assert not midi.exists()
