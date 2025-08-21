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
