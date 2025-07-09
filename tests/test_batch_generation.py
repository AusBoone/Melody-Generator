import importlib
import sys
import types
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_generate_batch_uses_process_pool(monkeypatch):
    """``generate_batch`` should create a ``ProcessPoolExecutor`` when workers>1."""

    # Provide lightweight stubs so the module imports without optional dependencies
    stub_mido = types.ModuleType("mido")

    class DummyMidiFile:
        def __init__(self, *a, **k):
            self.tracks = []

        def save(self, _):
            pass

    stub_mido.Message = lambda *a, **k: None
    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = list
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    monkeypatch.setitem(sys.modules, "mido", stub_mido)

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    calls = {}

    class DummyExec:
        def __init__(self, max_workers=None):
            calls["workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def submit(self, fn, cfg):
            class DummyFut:
                def result(self_inner):
                    return fn(cfg)

            return DummyFut()

    batch = importlib.import_module("melody_generator.batch_generation")

    monkeypatch.setattr(batch, "ProcessPoolExecutor", DummyExec)
    monkeypatch.setattr(
        batch, "generate_melody", lambda **kw: [kw["key"]] * kw["num_notes"]
    )

    configs = [
        {
            "key": "C",
            "num_notes": 2,
            "chord_progression": ["C"],
            "motif_length": 1,
        },
        {
            "key": "D",
            "num_notes": 2,
            "chord_progression": ["D"],
            "motif_length": 1,
        },
    ]

    res = batch.generate_batch(configs, workers=2)

    assert calls["workers"] == 2
    assert res == [["C", "C"], ["D", "D"]]


def test_generate_batch_negative_workers(monkeypatch):
    """Negative worker counts should raise ``ValueError``."""

    batch = importlib.import_module("melody_generator.batch_generation")

    # ``generate_melody`` is a lightweight stub so the test focuses solely on
    # argument validation inside ``generate_batch``.
    monkeypatch.setattr(batch, "generate_melody", lambda **kw: [])

    with pytest.raises(ValueError):
        batch.generate_batch([], workers=-1)


def test_generate_batch_zero_workers(monkeypatch):
    """``0`` workers should raise ``ValueError`` for clarity."""

    batch = importlib.import_module("melody_generator.batch_generation")

    # ``generate_melody`` is a lightweight stub so the test focuses solely on
    # argument validation inside ``generate_batch``.
    monkeypatch.setattr(batch, "generate_melody", lambda **kw: [])

    with pytest.raises(ValueError):
        batch.generate_batch([], workers=0)
