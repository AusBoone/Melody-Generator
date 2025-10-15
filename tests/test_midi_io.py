"""Unit tests for ``midi_io``'s behaviour and error handling.

The suite verifies two key aspects:

* ``create_midi_file`` returns a ``MidiFile`` instance when the ``mido``
  dependency is available. This ensures callers can rely on the object type for
  further processing or inspection without reloading the written file.
* ``create_midi_file`` provides a helpful message when the optional ``mido``
  dependency is absent. ``monkeypatch`` simulates the module being unavailable so
  the function's error path can be exercised without manipulating the
  environment.

Example
-------
>>> from melody_generator import midi_io
>>> midi_io.create_midi_file(["C4"], 120, (4, 4), "out.mid")
"""

from __future__ import annotations

import importlib
import builtins
import sys
from pathlib import Path

import pytest

# Ensure the package is importable regardless of the current working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody_generator import midi_io  # noqa: E402  # isort:skip


def test_create_midi_file_returns_midifile(tmp_path):
    """``create_midi_file`` should return the ``MidiFile`` object it writes.

    A minimal one-note melody is rendered to a temporary path. The function
    returns the in-memory ``MidiFile`` instance so callers can further inspect
    or modify the result without reloading it from disk. The test asserts the
    returned object is of the expected type.
    """

    from mido import MidiFile

    out = tmp_path / "song.mid"
    mid = midi_io.create_midi_file(["C4"], 120, (4, 4), str(out))

    assert isinstance(mid, MidiFile)


def test_create_midi_file_missing_mido(monkeypatch, tmp_path):
    """Absent ``mido`` should raise ``ImportError`` with install guidance.

    The test removes ``mido`` from ``sys.modules`` and patches ``__import__`` to
    raise ``ModuleNotFoundError`` when ``mido`` is requested.  This simulates an
    environment where the optional dependency is not installed without modifying
    the global Python setup.  ``create_midi_file`` should then surface a clear
    message instructing the user how to resolve the issue.
    """

    # Remove any previously loaded ``mido`` modules to mimic a fresh environment.
    monkeypatch.delitem(sys.modules, "mido", raising=False)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mido":
            raise ModuleNotFoundError("No module named 'mido'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    out = tmp_path / "song.mid"

    with pytest.raises(ImportError, match="pip install mido"):
        midi_io.create_midi_file(["C4"], 120, (4, 4), str(out))


def test_create_midi_file_ornament_track(tmp_path):
    """Enabling ornaments should add a dedicated grace-note track."""

    # ``load_module`` test helpers replace ``mido`` with minimal stubs that
    # intentionally omit rich message objects. Ensure the real dependency is
    # available so ``create_midi_file`` emits genuine ``Message`` instances that
    # expose channel metadata for validation.
    sys.modules.pop("mido", None)
    mido_mod = importlib.import_module("mido")
    MidiFile = mido_mod.MidiFile

    out = tmp_path / "ornament.mid"
    melody = ["C4", "E4", "G4"]

    mid = midi_io.create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        ornaments=True,
    )

    assert isinstance(mid, MidiFile)
    # The ornament track is appended after the main melody track.
    ornament_track = mid.tracks[-1]

    program_msgs = [
        msg for msg in ornament_track if getattr(msg, "type", None) == "program_change"
    ]
    assert program_msgs, "ornament track should configure its own program"
    channel = getattr(program_msgs[0], "channel", None)
    if channel is None and hasattr(program_msgs[0], "dict"):
        channel = program_msgs[0].dict().get("channel")
    assert channel == midi_io.ORNAMENT_CHANNEL

    note_on_events = [msg for msg in ornament_track if getattr(msg, "type", None) == "note_on"]
    assert note_on_events, "ornament track should include grace-note placeholders"
    first = note_on_events[0]
    assert first.channel == midi_io.ORNAMENT_CHANNEL
    assert first.time >= 0
    # The placeholder should sit close to the melody pitch (within one step).
    assert abs(first.note - midi_io.note_to_midi(melody[0])) <= 2
