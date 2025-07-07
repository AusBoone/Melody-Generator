"""Unit tests for ``play_midi`` using a mocked FluidSynth backend.

These tests validate the realtime playback helper without requiring the real
``fluidsynth`` library.  A minimal ``Synth`` stub records method calls so the
function's behaviour can be asserted.  Additional tests simulate common failure
modes to ensure ``MidiPlaybackError`` is raised appropriately.

Example
-------
>>> from melody_generator.playback import play_midi
>>> play_midi("melody.mid", soundfont="/path/to/font.sf2")
"""

from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
import types
import subprocess

import pytest

# Ensure the package can be imported regardless of pytest's working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Provide lightweight stand-ins for optional dependencies so the playback module
# imports without requiring the real packages.
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
MidiPlaybackError = playback.MidiPlaybackError


class DummySynth:
    """Record calls made by ``play_midi`` for assertion."""

    last_instance: "DummySynth | None" = None

    def __init__(self) -> None:
        self.started = False
        self.sf_loaded: str | None = None
        self.program: tuple[int, int, int, int] | None = None
        self.played: str | None = None
        self.deleted = False
        DummySynth.last_instance = self

    def start(self) -> None:
        self.started = True

    def sfload(self, path: str) -> int:  # noqa: D401 - short summary
        """Pretend to load ``path`` and return a dummy SoundFont ID."""
        self.sf_loaded = path
        return 1

    def program_select(self, chan: int, sfid: int, bank: int, preset: int) -> None:
        self.program = (chan, sfid, bank, preset)

    def play_midi_file(self, path: str) -> None:
        self.played = path

    def delete(self) -> None:
        self.deleted = True


class FailStartSynth(DummySynth):
    """Variant that raises when ``start`` is called."""

    def start(self) -> None:  # type: ignore[override]
        raise RuntimeError("driver failure")


def test_play_midi_success(tmp_path, monkeypatch):
    """Playback should invoke FluidSynth methods without errors."""

    midi = tmp_path / "song.mid"
    midi.write_text("midi")

    # Avoid filesystem checks by bypassing ``_resolve_soundfont``
    monkeypatch.setattr(playback, "_resolve_soundfont", lambda sf: "font.sf2")
    monkeypatch.setitem(sys.modules, "fluidsynth", types.SimpleNamespace(Synth=DummySynth))

    playback.play_midi(str(midi))

    synth = DummySynth.last_instance
    assert synth is not None
    assert synth.started
    assert synth.sf_loaded == "font.sf2"
    assert synth.program == (0, 1, 0, 0)
    assert synth.played == str(midi)
    assert synth.deleted


def test_play_midi_import_failure(monkeypatch):
    """Missing ``fluidsynth`` module results in ``MidiPlaybackError``."""

    monkeypatch.delitem(sys.modules, "fluidsynth", raising=False)

    orig_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fluidsynth":
            raise ImportError("missing")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(MidiPlaybackError):
        playback.play_midi("dummy.mid")


def test_play_midi_bad_soundfont(monkeypatch):
    """Non-existent SoundFont paths raise ``MidiPlaybackError``."""

    monkeypatch.setitem(sys.modules, "fluidsynth", types.SimpleNamespace(Synth=DummySynth))

    with pytest.raises(MidiPlaybackError):
        playback.play_midi("dummy.mid", soundfont="/non/existent.sf2")


def test_play_midi_driver_start_failure(monkeypatch):
    """Errors starting the audio driver propagate as ``MidiPlaybackError``."""

    monkeypatch.setattr(playback, "_resolve_soundfont", lambda sf: "font.sf2")
    monkeypatch.setitem(sys.modules, "fluidsynth", types.SimpleNamespace(Synth=FailStartSynth))

    with pytest.raises(MidiPlaybackError):
        playback.play_midi("dummy.mid")



def test_render_midi_missing_file(tmp_path, monkeypatch):
    """``render_midi_to_wav`` should error when the MIDI file does not exist."""

    output = tmp_path / "song.wav"
    # Ensure SoundFont resolution succeeds so only the missing MIDI triggers
    # the failure.
    monkeypatch.setattr(playback, "_resolve_soundfont", lambda sf: "font.sf2")
    called = False

    def fake_run(*_a, **_k):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MidiPlaybackError, match="MIDI file not found"):
        playback.render_midi_to_wav("missing.mid", str(output))

    assert not called
