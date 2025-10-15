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


def test_generate_batch_async_requires_celery(monkeypatch):
    """Asynchronous helper should fail when Celery support is unavailable."""

    batch = importlib.import_module("melody_generator.batch_generation")
    # Ensure the module believes Celery is missing even if installed by the
    # environment running the tests.
    monkeypatch.setattr(batch, "Celery", None)
    monkeypatch.setattr(batch, "celery_app", None)

    configs = [
        {"key": "C", "num_notes": 1, "chord_progression": ["C"], "motif_length": 1}
    ]

    with pytest.raises(RuntimeError):
        batch.generate_batch_async(configs)


def test_generate_batch_async_dispatches_task(monkeypatch):
    """When provided a Celery app the async helper should queue the task."""

    batch = importlib.reload(importlib.import_module("melody_generator.batch_generation"))

    # Provide lightweight dependency stubs so the module can import.
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

    class DummyAsyncResult:
        """Mimics ``celery.result.AsyncResult`` for unit testing."""

        def __init__(self, payload):
            self.payload = payload

        def get(self, timeout=None):
            return self.payload

    class DummyTask:
        """Simple callable task storing ``apply_async`` invocations."""

        def __init__(self, func):
            self.func = func
            self.calls = []

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

        def apply_async(self, args=None, kwargs=None, countdown=None):
            args = args or []
            kwargs = kwargs or {}
            result = self.func(*args, **kwargs)
            self.calls.append({
                "args": args,
                "kwargs": kwargs,
                "countdown": countdown,
                "result": result,
            })
            return DummyAsyncResult(result)

    class DummyCelery:
        """Minimal stand-in implementing ``task`` and ``tasks`` mapping."""

        def __init__(self):
            self.tasks = {}

        def task(self, name=None):
            def decorator(func):
                task = DummyTask(func)
                self.tasks[name or func.__name__] = task
                return task

            return decorator

    dummy_app = DummyCelery()

    # Pretend Celery is installed and configure the helper with the dummy app.
    monkeypatch.setattr(batch, "Celery", DummyCelery)
    batch.configure_celery(dummy_app)

    monkeypatch.setattr(
        batch,
        "generate_melody",
        lambda **kw: [f"{kw['key']}" for _ in range(kw["num_notes"])],
    )

    configs = [
        {"key": "C", "num_notes": 2, "chord_progression": ["C"], "motif_length": 1},
        {"key": "G", "num_notes": 1, "chord_progression": ["G"], "motif_length": 1},
    ]

    result = batch.generate_batch_async(configs, countdown=3, celery_app=dummy_app)

    # The dummy task should have been registered under the expected name and
    # executed immediately by the fake ``apply_async``.
    task = dummy_app.tasks[batch._CELERY_TASK_NAME]
    assert task.calls[0]["countdown"] == 3
    assert result.get() == [["C", "C"], ["G"]]


def test_generate_batch_async_negative_countdown(monkeypatch):
    """Negative countdown values should be rejected with ``ValueError``."""

    batch = importlib.import_module("melody_generator.batch_generation")
    monkeypatch.setattr(batch, "Celery", object)
    monkeypatch.setattr(batch, "celery_app", object())

    with pytest.raises(ValueError):
        batch.generate_batch_async([], countdown=-1)
