"""Tests for the style embedding helpers."""

import importlib
import sys
from pathlib import Path
import types

# Ensure the repository root is on ``sys.path`` so the package imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

style = importlib.import_module("melody_generator.style_embeddings")


def test_style_vector_lookup():
    """Known style names should return fixed-length vectors."""
    vec = style.get_style_vector("jazz")
    assert getattr(vec, "shape", (len(vec),))[0] == 3


def test_set_and_get_active_style():
    """``set_style`` should store and return the vector provided."""

    style.set_style([0.2, 0.3, 0.5])
    vec = style.get_active_style()
    assert list(vec) == [0.2, 0.3, 0.5]
    style.set_style(None)


def test_interpolate_vectors():
    """Interpolating half way should average the inputs."""

    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 0.0, 1.0]
    result = style.interpolate_vectors(v1, v2, 0.5)
    assert result[0] == result[2] == 0.5


def test_extract_style_invokes_model(monkeypatch, tmp_path):
    """``extract_style`` must call ``encode`` on the provided VAE."""

    class DummyMidi:
        def __init__(self):
            self.tracks = [[]]

    mido_stub = types.ModuleType("mido")
    mido_stub.MidiFile = lambda p: DummyMidi()
    monkeypatch.setitem(sys.modules, "mido", mido_stub)

    called = {}

    class DummyVAE:
        def encode(self, notes):
            called["notes"] = list(notes)
            return [0.1, 0.2, 0.3]

    midi = tmp_path / "test.mid"
    midi.write_text("dummy")
    vec = style.extract_style(str(midi), DummyVAE())
    assert called["notes"] == []
    assert list(vec) == [0.1, 0.2, 0.3]


def test_generate_melody_uses_active_style(monkeypatch):
    """``generate_melody`` should consult the active style vector."""

    mg = importlib.import_module("melody_generator")

    style.set_style([2.0] + [0.0] * (len(mg.SCALE["C"]) - 1))

    calls = {"count": 0}

    def fake_get():
        calls["count"] += 1
        return style.get_active_style()

    monkeypatch.setattr(mg, "get_active_style", fake_get)
    mg.generate_melody("C", 4, ["C"], motif_length=2)
    assert calls["count"] > 0
    style.set_style(None)

