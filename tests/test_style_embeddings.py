"""Tests for the style embedding helpers."""

import importlib
import json
import sys
from pathlib import Path
import types
import pytest

# Ensure the repository root is on ``sys.path`` so the package imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Provide a minimal ``mido`` stub so importing the package does not fail.
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
class _DummyMidiFile:
    """Minimal ``MidiFile`` stub used during import."""

    def __init__(self, *_, **__):
        self.tracks = []


stub_mido.MidiFile = _DummyMidiFile
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *a, **kw: object()
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

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


def test_vectors_are_copied():
    """Returned style vectors should not expose internal state."""

    vec = style.get_style_vector("jazz")
    vec[0] = 99
    # Fetch the vector again; it should remain unmodified
    fresh = style.get_style_vector("jazz")
    assert list(fresh)[0] != 99

    style.set_style([0.1, 0.2, 0.3])
    active = style.get_active_style()
    active[0] = 42
    assert style.get_active_style()[0] != 42


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


def test_module_without_numpy(monkeypatch):
    """Fallback logic should work when numpy is unavailable."""

    monkeypatch.setitem(sys.modules, "numpy", None)
    style_no_np = importlib.reload(importlib.import_module("melody_generator.style_embeddings"))

    vec = style_no_np.get_style_vector("pop")
    assert vec == [0.0, 0.0, 1.0]

    blended = style_no_np.blend_styles("baroque", "pop", 0.5)
    assert blended == [0.5, 0.0, 0.5]

    style_no_np.set_style([0.1, 0.2, 0.3])
    assert style_no_np.get_active_style() == [0.1, 0.2, 0.3]

    with pytest.raises(RuntimeError):
        style_no_np.StyleVAE()

    # Reload module so later tests use the original NumPy-backed version
    importlib.reload(style)


def test_load_styles_json(tmp_path):
    """New styles loaded from JSON should be retrievable."""

    path = tmp_path / "styles.json"
    path.write_text(json.dumps({"blues": [0.3, 0.3, 0.4]}))
    style.load_styles(str(path))
    assert list(style.get_style_vector("blues")) == [0.3, 0.3, 0.4]


def test_load_styles_invalid_format(tmp_path):
    """Invalid style files must raise ``ValueError``."""

    bad = tmp_path / "bad.json"
    bad.write_text("[]")  # Not a mapping
    with pytest.raises(ValueError):
        style.load_styles(str(bad))


def test_load_styles_yaml(tmp_path):
    """Styles defined in YAML files should load correctly."""

    pytest.importorskip(
        "yaml"
    )  # Skip test entirely when optional PyYAML is missing

    # Create a minimal YAML file defining an extra style vector
    path = tmp_path / "styles.yaml"
    path.write_text("folk: [0.1, 0.6, 0.3]\n")

    style.load_styles(str(path))
    # Verify the new style can be retrieved just like built-in presets.
    # ``list`` ensures equality regardless of NumPy usage internally.
    assert list(style.get_style_vector("folk")) == [0.1, 0.6, 0.3]


def test_load_styles_dimension_mismatch(tmp_path):
    """Vectors of differing lengths should trigger ``ValueError`` and not modify presets."""

    # Prepare a JSON file that mixes a valid 3D vector with an invalid 4D one.
    path = tmp_path / "bad_dim.json"
    path.write_text(json.dumps({"good": [0.1, 0.2, 0.7], "bad": [1, 2, 3, 4]}))

    # Snapshot the current presets so we can verify they remain untouched.
    before = dict(style.STYLE_VECTORS)

    # Loading should fail because "bad" has more dimensions than the existing presets.
    with pytest.raises(ValueError):
        style.load_styles(str(path))

    # Ensure neither of the new names were merged and existing presets were preserved.
    assert style.STYLE_VECTORS == before

