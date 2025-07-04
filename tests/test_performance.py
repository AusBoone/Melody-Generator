"""Tests for performance helpers and profiling utilities."""

import importlib
import io
import sys
import types
from pathlib import Path

import pytest

# Stub required modules so importing melody_generator works without optional deps.
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
stub_mido.MidiFile = object
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: object()
stub_mido.bpm2tempo = lambda bpm: bpm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    """Provide stand-in modules required for import."""

    monkeypatch.setitem(sys.modules, "mido", stub_mido)
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)



def test_compute_base_weights_basic():
    """Base weight computation should reflect transition and chord biases."""

    perf = importlib.import_module("melody_generator.performance")

    intervals = [0, 2, 7]
    chord_mask = [True, False, True]
    result = perf.compute_base_weights(intervals, chord_mask, 1)

    assert pytest.approx(result[0], rel=1e-5) == 1.44
    assert pytest.approx(result[1], rel=1e-5) == 0.64
    assert pytest.approx(result[2], rel=1e-5) == 0.06



def test_profile_context_records_stats():
    """The ``profile`` context manager should collect profiling data."""

    perf = importlib.import_module("melody_generator.performance")

    out = io.StringIO()
    with perf.profile(out) as pr:
        sum(range(10))
    # ``getstats`` returns a list of recorded function calls
    assert pr.getstats()
    assert "sum" in out.getvalue()

