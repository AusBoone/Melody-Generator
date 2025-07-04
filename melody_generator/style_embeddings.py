"""Minimal style embedding helpers for genre interpolation.

A real implementation would train a variational autoencoder (VAE) on MIDI
data to learn stylistic characteristics. This module provides static
embeddings purely for demonstration and testing.
"""

from __future__ import annotations

from typing import Dict

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
