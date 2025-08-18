"""Unit tests for the ``augment_sequences`` helper.

This module verifies that data augmentation correctly generates transposed and
optionally inverted copies of input pitch sequences.  It also checks error
handling when no sequences are provided, when a subsequence is empty, and that
custom transposition ranges are honoured.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

# Provide minimal stubs so the package imports without optional dependencies.
mido_stub = types.ModuleType("mido")
mido_stub.Message = object
mido_stub.MidiFile = object
mido_stub.MidiTrack = list
mido_stub.MetaMessage = lambda *a, **kw: object()
mido_stub.bpm2tempo = lambda bpm: bpm

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Insert stubs and reload the augmentation module for a clean import."""

    monkeypatch.setitem(sys.modules, "mido", mido_stub)
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    global aug
    aug = importlib.reload(importlib.import_module("melody_generator.augmentation"))


def test_augment_sequences_default_transposes_and_inverts():
    """Default parameters should create five transpositions and their inversions."""

    seq = [60, 62]

    result = aug.augment_sequences([seq])

    assert len(result) == 10

    for t in range(-2, 3):
        assert aug.transpose_sequence(seq, t) in result

    inverted = aug.invert_sequence(seq, seq[0])
    assert result.count(inverted) == 5


def test_augment_sequences_empty_input_error():
    """Passing an empty list of sequences should raise ``ValueError``."""

    with pytest.raises(ValueError):
        aug.augment_sequences([])


def test_augment_sequences_empty_subsequence_error():
    """Empty subsequences should raise ``ValueError`` to alert the caller."""

    with pytest.raises(ValueError):
        aug.augment_sequences([[]])


def test_augment_sequences_custom_transpose_range():
    """User-supplied ranges must control the transpositions applied."""

    seq = [60]
    tr = [0, 12]

    result = aug.augment_sequences([seq], transpose_range=tr)

    expected = []
    for t in tr:
        expected.append(aug.transpose_sequence(seq, t))
        expected.append(aug.invert_sequence(seq, seq[0]))

    assert result == expected
