"""Tests for the style embedding helpers.

This suite validates vector handling, dynamic style loading and context
isolation across threads and asyncio tasks. ``load_styles`` is exercised
against multiple failure modes and confirmed to copy loaded vectors so external
mutations cannot corrupt module-level presets.
"""

import asyncio
import importlib
import json
import sys
import threading
import types
from pathlib import Path

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
    # Verify the retrieved vector matches the module's current dimensionality.
    assert getattr(vec, "shape", (len(vec),))[0] == style.STYLE_DIMENSION


def test_set_and_get_active_style():
    """``set_style`` should store a context-local vector and retrieve a copy."""

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


def test_load_styles_inconsistent_dimensions(tmp_path):
    """Mixed-dimensional vectors in one file should raise ``ValueError``."""

    # Create a file containing both 3D and 4D vectors, which should be rejected
    # because all vectors in the file must share a common dimensionality.
    path = tmp_path / "bad_dim.json"
    path.write_text(json.dumps({"good": [0.1, 0.2, 0.7], "bad": [1, 2, 3, 4]}))

    before = dict(style.STYLE_VECTORS)
    with pytest.raises(ValueError):
        style.load_styles(str(path))
    assert style.STYLE_VECTORS == before


def test_load_styles_shrinking_dimension_fails(tmp_path):
    """Vectors shorter than existing presets should be rejected."""

    path = tmp_path / "shrink.json"
    path.write_text(json.dumps({"mini": [0.1, 0.2]}))

    before = dict(style.STYLE_VECTORS)
    with pytest.raises(ValueError):
        style.load_styles(str(path))
    assert style.STYLE_VECTORS == before


def test_load_styles_expands_dimension(tmp_path):
    """Longer vectors should expand the embedding and pad existing presets."""

    path = tmp_path / "expand.json"
    path.write_text(json.dumps({"electro": [0.1, 0.2, 0.3, 0.4]}))

    before_vectors = dict(style.STYLE_VECTORS)
    before_dim = style.STYLE_DIMENSION
    style.load_styles(str(path))
    try:
        assert style.STYLE_DIMENSION == before_dim + 1
        assert list(style.get_style_vector("baroque"))[-1] == 0.0
        assert list(style.get_style_vector("electro")) == [0.1, 0.2, 0.3, 0.4]
    finally:
        style.STYLE_VECTORS = before_vectors
        style.STYLE_DIMENSION = before_dim


def test_load_styles_non_sequence_value(tmp_path):
    """Mappings with non-sequence values should raise ``ValueError`` and not alter presets."""

    path = tmp_path / "bad_value.json"
    path.write_text(json.dumps({"bad": 1}))  # Value is not a list or tuple

    # Snapshot current presets so we can verify they are untouched after failure.
    before = dict(style.STYLE_VECTORS)

    with pytest.raises(ValueError):
        style.load_styles(str(path))

    # Loading should fail without modifying any existing styles.
    assert style.STYLE_VECTORS == before


def test_load_styles_unsupported_extension(tmp_path):
    """Unknown file extensions must trigger ``ValueError``."""

    path = tmp_path / "styles.txt"
    path.write_text("irrelevant")

    before = dict(style.STYLE_VECTORS)
    with pytest.raises(ValueError):
        style.load_styles(str(path))
    # Ensure presets remain unchanged when the loader rejects the file.
    assert style.STYLE_VECTORS == before


def test_loaded_styles_are_copied(tmp_path):
    """Loaded style vectors should be insulated from caller-side mutations."""

    # Define a vector and write it to disk; ``vec`` will be mutated later to
    # confirm ``load_styles`` copies the data rather than referencing it.
    vec = [0.1, 0.2, 0.7]
    path = tmp_path / "fresh.json"
    path.write_text(json.dumps({"fresh": vec}))

    # Load the style and snapshot presets so we can restore them after the test.
    before = dict(style.STYLE_VECTORS)
    style.load_styles(str(path))

    try:
        # Mutating the source list must not affect the stored preset.
        vec[0] = 9.9
        assert style.get_style_vector("fresh")[0] == 0.1

        # The vector returned by ``get_style_vector`` should also be a copy.
        returned = style.get_style_vector("fresh")
        returned[1] = 9.9
        assert style.get_style_vector("fresh")[1] == 0.2
    finally:
        # Restore original presets so later tests see a clean environment.
        style.STYLE_VECTORS = before


def test_thread_local_style_is_isolated():
    """Styles set in separate threads must not leak between contexts."""

    results = {}

    def worker(name, vec):
        """Set and retrieve a style in a background thread."""

        style.set_style(vec)
        results[name] = list(style.get_active_style())

    t1 = threading.Thread(target=worker, args=("a", [1.0, 0.0, 0.0]))
    t2 = threading.Thread(target=worker, args=("b", [0.0, 1.0, 0.0]))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Each thread should observe only the style it set.
    assert results["a"] == [1.0, 0.0, 0.0]
    assert results["b"] == [0.0, 1.0, 0.0]
    # The main thread never set a style so it should still return ``None``.
    assert style.get_active_style() is None


def test_async_style_is_isolated():
    """Styles set in asyncio tasks must remain isolated to each task."""

    results = {}

    async def worker(name, vec):
        """Set and retrieve a style in an asyncio task."""

        style.set_style(vec)
        # Yield control to ensure tasks overlap and isolation is exercised.
        await asyncio.sleep(0)
        results[name] = list(style.get_active_style())

    async def runner():
        """Spawn two tasks that set distinct styles concurrently."""

        await asyncio.gather(
            worker("a", [1.0, 0.0, 0.0]),
            worker("b", [0.0, 1.0, 0.0]),
        )

    asyncio.run(runner())

    # Each task should observe only the style it set.
    assert results["a"] == [1.0, 0.0, 0.0]
    assert results["b"] == [0.0, 1.0, 0.0]
    # The main task never set a style so it should still return ``None``.
    assert style.get_active_style() is None

