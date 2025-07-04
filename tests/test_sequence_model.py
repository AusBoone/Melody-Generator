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

# Stub ``mido`` and ``tkinter`` so importing ``melody_generator`` succeeds
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
stub_mido.MidiFile = object
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: object()
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

seq_mod = importlib.reload(importlib.import_module("melody_generator.sequence_model"))


def test_predict_next_requires_history():
    """``predict_next`` should validate that history is non-empty."""

    class DummyModel:
        def predict_logits(self, history):
            return [0.0, 0.0]

    with pytest.raises(ValueError):
        seq_mod.predict_next(DummyModel(), [])


def test_predict_next_returns_argmax():
    """Highest scoring index should be returned."""

    class DummyModel:
        def __init__(self):
            self.seen = []

        def predict_logits(self, history):
            self.seen.append(tuple(history))
            return [0.1, 0.9]

    model = DummyModel()
    result = seq_mod.predict_next(model, [1])
    assert result == 1
    assert model.seen == [(1,)]


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


def test_generate_melody_invokes_sequence_model():
    """``generate_melody`` should consult the provided sequence model."""

    mg = importlib.import_module("melody_generator")

    class DummyModel:
        def __init__(self):
            self.calls = 0

        def predict_logits(self, history):
            self.calls += 1
            # Strongly favour scale degree 0
            return [2.0] + [0.0] * (len(mg.SCALE["C"]) - 1)

    model = DummyModel()
    # ``motif_length`` greater than one ensures the generation loop runs a
    # branch that consults the sequence model.
    mg.generate_melody("C", 4, ["C"], motif_length=2, sequence_model=model)
    assert model.calls > 0


def test_quantize_onnx_model_called(monkeypatch):
    """``quantize_onnx_model`` should call ONNX Runtime's helper."""

    quant_mod = types.ModuleType("quantization")
    called = {}

    def fake_quantize(model_input, model_output, weight_type=None):
        called["args"] = (model_input, model_output, weight_type)

    quant_mod.quantize_dynamic = fake_quantize
    quant_mod.QuantType = types.SimpleNamespace(QInt8="qint8")
    ort_stub = types.ModuleType("onnxruntime")
    ort_stub.quantization = quant_mod
    monkeypatch.setitem(sys.modules, "onnxruntime", ort_stub)
    monkeypatch.setitem(sys.modules, "onnxruntime.quantization", quant_mod)

    seq = importlib.reload(importlib.import_module("melody_generator.sequence_model"))
    seq.quantize_onnx_model("in.onnx", "out.onnx")

    assert called["args"][0] == "in.onnx"
    assert called["args"][1] == "out.onnx"
    assert called["args"][2] == quant_mod.QuantType.QInt8


def test_quantize_onnx_model_requires_runtime(monkeypatch):
    """An informative error should be raised when ONNX Runtime is missing."""

    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    monkeypatch.setitem(sys.modules, "onnxruntime.quantization", None)
    seq = importlib.reload(importlib.import_module("melody_generator.sequence_model"))

    with pytest.raises(RuntimeError):
        seq.quantize_onnx_model("model.onnx", "quant.onnx")
