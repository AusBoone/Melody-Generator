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


def test_compute_base_weights_validates_lengths():
    """Mismatched interval/mask lengths should raise ``ValueError``."""

    perf = importlib.import_module("melody_generator.performance")

    with pytest.raises(ValueError):
        # Provide an extra mask entry to trigger the alignment validation.
        perf.compute_base_weights([0, 2], [True, False, True], prev_interval=1)


def test_compute_base_weights_rejects_negative_intervals():
    """Negative interval magnitudes are invalid and should error."""

    perf = importlib.import_module("melody_generator.performance")

    with pytest.raises(ValueError):
        # Negative magnitudes imply an error in the caller's preprocessing.
        perf.compute_base_weights([-1, 2], [True, False], prev_interval=1)


def test_profile_honours_limit_argument(monkeypatch):
    """Custom ``limit`` should be forwarded to ``pstats.Stats.print_stats``."""

    perf = importlib.import_module("melody_generator.performance")

    import pstats

    captured = {}

    def fake_print_stats(self, *args, **kwargs):
        """Record arguments passed to ``print_stats`` for assertion."""

        captured["args"] = args
        captured["kwargs"] = kwargs
        return original_print_stats(self, *args, **kwargs)

    original_print_stats = pstats.Stats.print_stats
    monkeypatch.setattr(pstats.Stats, "print_stats", fake_print_stats)

    out = io.StringIO()
    with perf.profile(out, limit=5) as pr:
        sum(range(5))
    assert pr.getstats()
    # ``args`` should contain the custom limit value provided above.
    assert captured.get("args") == (5,)

    # ``limit=None`` should call ``print_stats`` with no positional arguments.
    captured.clear()
    with perf.profile(out, limit=None) as pr:
        sum(range(6))
    assert pr.getstats()
    assert captured.get("args") == ()

