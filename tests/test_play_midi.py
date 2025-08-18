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

# Revision note
# -------------
# A test for ``Synth.play_midi_file`` failures was added to ensure the wrapper
# propagates error messages via ``MidiPlaybackError``. The ``FailPlaySynth``
# class simulates this scenario without relying on the real FluidSynth library.

from __future__ import annotations

import builtins
import importlib
import logging
import subprocess
import sys
import types
from pathlib import Path

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


class FailPlaySynth(DummySynth):
    """Variant that raises when ``play_midi_file`` is invoked."""

    def play_midi_file(self, path: str) -> None:  # type: ignore[override]
        raise RuntimeError("synthesis error")


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


def test_play_midi_playback_failure(monkeypatch):
    """Playback errors should surface the original message for debugging.

    ``DummySynth``'s ``play_midi_file`` method is forced to raise an
    exception to mimic a synth failure.  ``play_midi`` should wrap this
    error in ``MidiPlaybackError`` while preserving the message.
    """

    # Bypass soundfont resolution to focus solely on the playback failure.
    monkeypatch.setattr(playback, "_resolve_soundfont", lambda sf: "font.sf2")
    monkeypatch.setitem(
        sys.modules,
        "fluidsynth",
        types.SimpleNamespace(Synth=FailPlaySynth),
    )

    with pytest.raises(MidiPlaybackError, match="synthesis error"):
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


def test_cli_playback_error_logs_and_falls_back(monkeypatch, tmp_path, caplog):
    """CLI should log playback errors and use default player as a fallback.

    ``run_cli`` previews the generated MIDI when ``--play`` is supplied. If
    FluidSynth is unavailable or ``play_midi`` fails, the exception should be
    logged for debugging while ``_open_default_player`` is invoked so the user
    can still hear the output. This test simulates that failure path by forcing
    ``play_midi`` to raise and asserting both behaviours occur.
    """

    import melody_generator as mg
    import melody_generator.cli as cli

    midi_path = tmp_path / "out.mid"

    # Minimal stub for ``create_midi_file`` to avoid heavy MIDI handling.
    monkeypatch.setattr(mg, "create_midi_file", lambda *a, **k: None)
    # Ensure melody generation returns deterministic output.
    monkeypatch.setattr(mg, "generate_melody", lambda *a, **k: ["C4"])

    # Force ``play_midi`` to fail so the fallback path is exercised.
    def fail_play(*_a, **_k):
        raise RuntimeError("synthesis boom")

    monkeypatch.setattr(playback, "play_midi", fail_play)

    # Capture invocations of the default player helper.
    opened: list[str] = []
    monkeypatch.setattr(mg, "_open_default_player", lambda path: opened.append(path))

    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--output",
        str(midi_path),
        "--play",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with caplog.at_level(logging.ERROR):
        cli.run_cli()

    # The default player should be invoked with the output path.
    assert opened == [str(midi_path)]
    # The error message should be present in the logs for debugging.
    assert "synthesis boom" in caplog.text
