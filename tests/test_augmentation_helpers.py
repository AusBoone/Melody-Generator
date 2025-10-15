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
    """Default augmentation should return ordered transpose/inversion pairs."""

    seq = [60, 62]

    result = aug.augment_sequences([seq])

    # Five transpositions each produce two entries (transposed + inverted).
    assert len(result) == 10

    expected: list[list[int]] = []
    for t in range(-2, 3):
        # Each pair should be musically related: inversion mirrors the
        # transposed sequence around its own pivot.
        transposed = aug.transpose_sequence(seq, t)
        inverted = aug.invert_sequence(transposed, transposed[0])
        expected.extend([transposed, inverted])

    assert result == expected


def test_augment_sequences_empty_input_error():
    """Passing an empty list of sequences should raise ``ValueError``."""

    with pytest.raises(ValueError):
        aug.augment_sequences([])


def test_augment_sequences_empty_subsequence_error():
    """Empty subsequences should raise ``ValueError`` to alert the caller."""

    with pytest.raises(ValueError):
        aug.augment_sequences([[]])


def test_augment_sequences_custom_transpose_range():
    """Custom ranges should dictate transpose order and matching inversions."""

    seq = [60]
    tr = [0, 12]

    result = aug.augment_sequences([seq], transpose_range=tr)

    expected: list[list[int]] = []
    for t in tr:
        transposed = aug.transpose_sequence(seq, t)
        expected.append(transposed)
        expected.append(aug.invert_sequence(transposed, transposed[0]))

    assert result == expected


def test_augment_sequences_inversions_follow_transpose_pivot():
    """Inversions must mirror the transposed sequence rather than the original."""

    seq = [60, 64]
    # ``12`` raises the line by an octave so the correct inversion should be
    # centred around 72 instead of the original 60.
    result = aug.augment_sequences([seq], transpose_range=[12])

    transposed = aug.transpose_sequence(seq, 12)
    expected_inversion = aug.invert_sequence(transposed, transposed[0])
    unexpected_inversion = aug.invert_sequence(seq, seq[0])

    assert result == [transposed, expected_inversion]
    assert unexpected_inversion not in result
