"""Tests for data augmentation and transfer learning utilities."""

import importlib
import sys
import types
from pathlib import Path
import pytest

# Stub ``torch`` so augmentation imports without real PyTorch.
torch_stub = types.ModuleType("torch")
torch_stub.nn = types.ModuleType("nn")
torch_stub.nn.Module = object

def _tensor(data, dtype=None):
    return data

def _no_grad():
    class Ctx:
        def __enter__(self):
            pass
        def __exit__(self, exc_type, exc, tb):
            pass
    return Ctx()

torch_stub.tensor = _tensor
torch_stub.no_grad = _no_grad
# Provide ``randint`` and ``softmax`` used elsewhere
torch_stub.randint = lambda *a, **kw: "dummy"
torch_stub.softmax = lambda x, dim=0: [0.5, 0.5]
torch_stub.long = int

# Optimiser stub that records ``step`` calls
class DummyOptim:
    def __init__(self, params, lr=0.001):
        self.steps = 0
    def zero_grad(self):
        pass
    def step(self):
        self.steps += 1

# ``CrossEntropyLoss`` stub simply returns an int so ``backward`` can be called
class DummyLoss:
    def __call__(self, logits, target):
        return types.SimpleNamespace(backward=lambda: None)

torch_stub.optim = types.SimpleNamespace(Adam=lambda params, lr=0.001: DummyOptim(params, lr))
torch_stub.nn.CrossEntropyLoss = lambda: DummyLoss()

torch_stub.onnx = types.SimpleNamespace(export=lambda *a, **kw: kw)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stubs for MIDI and GUI modules
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
    """Inject stubs so imports succeed."""

    monkeypatch.setitem(sys.modules, "torch", torch_stub)
    monkeypatch.setitem(sys.modules, "mido", mido_stub)
    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tk_stub.filedialog)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tk_stub.messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", tk_stub.ttk)

    global aug
    aug = importlib.reload(importlib.import_module("melody_generator.augmentation"))


def test_transpose_sequence_clamps_range():
    """Notes should stay within the MIDI range after transposition."""

    result = aug.transpose_sequence([126, 127], 2)
    assert result == [127, 127]


def test_invert_sequence_basic():
    """Simple inversion around a pivot should mirror intervals."""

    result = aug.invert_sequence([60, 64], 60)
    assert result == [60, 56]


def test_perturb_rhythm_bounds():
    """Durations must remain positive after jitter is applied."""

    out = aug.perturb_rhythm([0.5, 0.5], jitter=0.1)
    assert all(d > 0 for d in out)


def test_fine_tune_model_steps_optimizer():
    """``fine_tune_model`` should call ``step`` on the optimiser."""

    class DummyModel:
        def __call__(self, data):
            return [0.0, 0.0]
        def parameters(self):
            return []

    opt = DummyOptim([])
    torch_stub.optim.Adam = lambda params, lr=0.001: opt
    aug.fine_tune_model(DummyModel(), [[0, 1, 2]], epochs=1)
    assert opt.steps > 0

