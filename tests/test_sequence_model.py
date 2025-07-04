"""Tests for the sequence model helpers."""

import importlib
import sys
import types
from pathlib import Path

import pytest

# Stub ``torch`` so the sequence model can import without PyTorch installed.
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
torch_stub.softmax = lambda x, dim=0: [0.5, 0.5]
torch_stub.no_grad = _no_grad
torch_stub.randint = lambda *args, **kwargs: "dummy"
torch_stub.onnx = types.SimpleNamespace(export=lambda *a, **kw: kw)
sys.modules.setdefault("torch", torch_stub)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

seq_mod = importlib.reload(importlib.import_module("melody_generator.sequence_model"))


def test_predict_next_requires_history():
    """``predict_next`` should validate that history is non-empty."""
    model = types.SimpleNamespace()
    with pytest.raises(ValueError):
        seq_mod.predict_next(model, [])


def test_export_onnx_called():
    """``export_onnx`` should invoke ``torch.onnx.export``."""

    class DummyModel:
        embed = types.SimpleNamespace(num_embeddings=5)

    called = {}

    def fake_export(model, dummy, path, **kwargs):
        called['args'] = (model, dummy, path)

    torch_stub.onnx.export = fake_export
    seq_mod.export_onnx(DummyModel(), "out.onnx", seq_len=2)
    assert called['args'][2] == "out.onnx"
