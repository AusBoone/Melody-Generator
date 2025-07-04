"""Style embedding helpers and lightweight VAE implementation.

Real deployments would train a full MusicVAE model on a large corpus of MIDI
files.  To keep the library self‑contained this module offers only minimal
utilities: a tiny :class:`StyleVAE` for demonstrations, functions for setting
an active style vector, interpolation helpers and a way to extract a style
embedding from a reference MIDI file.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    import types

    class _Array(list):
        @property
        def shape(self):  # mimic numpy.ndarray
            return (len(self),)

    def _array(val, dtype=None):
        return _Array(val)

    np = types.SimpleNamespace(array=_array)


STYLE_VECTORS: Dict[str, np.ndarray] = {
    "baroque": np.array([1.0, 0.0, 0.0], dtype=float),
    "jazz": np.array([0.0, 1.0, 0.0], dtype=float),
    "pop": np.array([0.0, 0.0, 1.0], dtype=float),
}

# Global style vector applied when ``set_style`` is called.
_ACTIVE_STYLE: Optional[np.ndarray] = None


def get_style_vector(name: str) -> np.ndarray:
    """Return the embedding vector for ``name``.

    Raises
    ------
    KeyError
        If ``name`` does not exist in :data:`STYLE_VECTORS`.
    """

    return STYLE_VECTORS[name]


def blend_styles(a: str, b: str, ratio: float) -> np.ndarray:
    """Linearly interpolate between two styles."""

    if not 0 <= ratio <= 1:
        raise ValueError("ratio must be between 0 and 1")
    return (1 - ratio) * get_style_vector(a) + ratio * get_style_vector(b)


def set_style(vec: Optional[Iterable[float]]) -> None:
    """Set the global style vector used during melody generation.

    Passing ``None`` clears the active style so note weights are unaffected.
    """

    global _ACTIVE_STYLE
    if vec is None:
        _ACTIVE_STYLE = None
        return
    _ACTIVE_STYLE = np.array(list(vec), dtype=float)


def get_active_style() -> Optional[np.ndarray]:
    """Return the style vector previously set via :func:`set_style`."""

    return _ACTIVE_STYLE


def interpolate_vectors(a: Iterable[float], b: Iterable[float], ratio: float) -> np.ndarray:
    """Blend two style vectors regardless of their named presets."""

    if not 0 <= ratio <= 1:
        raise ValueError("ratio must be between 0 and 1")
    if np.__class__.__name__ == "SimpleNamespace":  # numpy unavailable
        va = list(map(float, a))
        vb = list(map(float, b))
        if len(va) != len(vb):
            raise ValueError("style vectors must have the same dimensions")
        blended = [(1 - ratio) * x + ratio * y for x, y in zip(va, vb)]
        return np.array(blended)
    va = np.array(list(a), dtype=float)
    vb = np.array(list(b), dtype=float)
    if va.shape != vb.shape:
        raise ValueError("style vectors must have the same dimensions")
    return (1 - ratio) * va + ratio * vb


class StyleVAE:
    """Simplified VAE used to encode MIDI into a style embedding."""

    def __init__(self, latent_dim: int = 3) -> None:
        if np is None:
            raise RuntimeError("numpy is required for StyleVAE")
        self.latent_dim = latent_dim
        self._weights = np.random.default_rng().standard_normal((latent_dim,))

    def encode(self, notes: np.ndarray) -> np.ndarray:
        """Return a latent vector summarising ``notes``."""

        if notes.size == 0:
            notes = np.array([60], dtype=float)
        mean = float(np.mean(notes)) / 127.0
        return mean * self._weights

    def decode(self, z: np.ndarray) -> np.ndarray:  # pragma: no cover - simple demo
        """Invert :meth:`encode` (dummy implementation)."""

        return z * 127.0


def extract_style(midi_path: str, vae: "StyleVAE") -> np.ndarray:
    """Return a style embedding from ``midi_path`` using ``vae``."""

    import mido  # imported lazily to avoid mandatory dependency

    midi = mido.MidiFile(midi_path)
    notes = [
        msg.note
        for track in midi.tracks
        for msg in track
        if getattr(msg, "type", None) == "note_on" and getattr(msg, "velocity", 0) > 0
    ]
    return vae.encode(np.array(notes, dtype=float))
