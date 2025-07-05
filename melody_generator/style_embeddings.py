"""Style embedding helpers and lightweight VAE implementation.

Real deployments would train a full MusicVAE model on a large corpus of MIDI
files. To keep the library self-contained this module offers only minimal
utilities: a tiny :class:`StyleVAE` for demonstrations, functions for setting
an active style vector, interpolation helpers and a way to extract a style
embedding from a reference MIDI file.

``STYLE_VECTORS`` is now defined unconditionally for better static analysis and
helper functions return copies rather than references so callers cannot mutate
module-level state by accident.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

try:  # Attempt to use numpy when available for vector operations
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

# Convenience flag used throughout the module
USE_NUMPY = np is not None


# Store preset style vectors either as ``numpy.ndarray`` when available or simple
# ``list`` objects otherwise. Only a small set is provided for demonstration
# purposes. ``STYLE_VECTORS`` is defined unconditionally so static type checkers
# see a single assignment.
STYLE_VECTORS: Dict[str, Sequence[float]]
if USE_NUMPY:
    STYLE_VECTORS = {
        "baroque": np.array([1.0, 0.0, 0.0], dtype=float),
        "jazz": np.array([0.0, 1.0, 0.0], dtype=float),
        "pop": np.array([0.0, 0.0, 1.0], dtype=float),
    }
else:
    STYLE_VECTORS = {
        "baroque": [1.0, 0.0, 0.0],
        "jazz": [0.0, 1.0, 0.0],
        "pop": [0.0, 0.0, 1.0],
    }

# Global style vector applied when ``set_style`` is called.
_ACTIVE_STYLE: Optional[Sequence[float]] = None


def get_style_vector(name: str) -> Sequence[float]:
    """Return the embedding vector for ``name`` as a new sequence.

    Raises
    ------
    KeyError
        If ``name`` does not exist in :data:`STYLE_VECTORS`.
    """

    vec = STYLE_VECTORS[name]
    if USE_NUMPY:
        return np.array(vec, dtype=float)
    return list(vec)


def blend_styles(a: str, b: str, ratio: float) -> Sequence[float]:
    """Return a new vector midway between ``a`` and ``b``."""

    if not 0 <= ratio <= 1:
        raise ValueError("ratio must be between 0 and 1")
    # Fetch copies of the preset vectors so interpolation does not mutate the
    # originals.
    vec_a = get_style_vector(a)
    vec_b = get_style_vector(b)
    if USE_NUMPY:
        return (1 - ratio) * np.array(vec_a, dtype=float) + ratio * np.array(vec_b, dtype=float)
    if len(vec_a) != len(vec_b):
        raise ValueError("style vectors must have the same dimensions")
    return [(1 - ratio) * x + ratio * y for x, y in zip(vec_a, vec_b)]


def set_style(vec: Optional[Iterable[float]]) -> None:
    """Set the global style vector used during melody generation.

    Passing ``None`` clears the active style so note weights are unaffected.
    The provided iterable is converted to a plain list or ``numpy.ndarray`` to
    decouple external mutations from internal state.
    """

    global _ACTIVE_STYLE
    if vec is None:
        _ACTIVE_STYLE = None
        return
    # Convert to a concrete container so subsequent caller mutations do not
    # affect the stored style.
    _ACTIVE_STYLE = (
        np.array(list(vec), dtype=float)
        if USE_NUMPY
        else [float(v) for v in vec]
    )


def get_active_style() -> Optional[Sequence[float]]:
    """Return the style vector previously set via :func:`set_style`.

    A copy is returned to prevent accidental mutation of the global state.
    """

    if _ACTIVE_STYLE is None:
        return None
    return np.array(_ACTIVE_STYLE, dtype=float) if USE_NUMPY else list(_ACTIVE_STYLE)


def interpolate_vectors(a: Iterable[float], b: Iterable[float], ratio: float) -> Sequence[float]:
    """Blend two arbitrary vectors using ``ratio``."""

    if not 0 <= ratio <= 1:
        raise ValueError("ratio must be between 0 and 1")
    if USE_NUMPY:
        # Convert any iterable input to ``numpy.ndarray`` for vector math.
        va = np.array(list(a), dtype=float)
        vb = np.array(list(b), dtype=float)
        if va.shape != vb.shape:
            raise ValueError("style vectors must have the same dimensions")
        return (1 - ratio) * va + ratio * vb
    # Fallback path using lists when ``numpy`` is unavailable.
    va = list(map(float, a))
    vb = list(map(float, b))
    if len(va) != len(vb):
        raise ValueError("style vectors must have the same dimensions")
    return [(1 - ratio) * x + ratio * y for x, y in zip(va, vb)]


class StyleVAE:
    """Simplified VAE used to encode MIDI into a style embedding."""

    def __init__(self, latent_dim: int = 3) -> None:
        if not USE_NUMPY:
            raise RuntimeError("numpy is required for StyleVAE")
        self.latent_dim = latent_dim
        self._weights = np.random.default_rng().standard_normal((latent_dim,))

    def encode(self, notes: np.ndarray) -> np.ndarray:
        """Return a latent vector summarising ``notes``.

        The implementation is intentionally simple: the mean note value is
        normalised and scaled by randomly initialised weights.
        """

        if notes.size == 0:
            notes = np.array([60], dtype=float)
        mean = float(np.mean(notes)) / 127.0
        return mean * self._weights

    def decode(self, z: np.ndarray) -> np.ndarray:  # pragma: no cover - simple demo
        """Invert :meth:`encode` (dummy implementation).

        This mirrors :meth:`encode` by performing a simple linear scaling. It is
        not meant to produce realistic MIDI data.
        """

        return z * 127.0


def extract_style(midi_path: str, vae: "StyleVAE") -> Sequence[float]:
    """Return a style embedding from ``midi_path`` using ``vae``.

    The MIDI file is parsed for ``note_on`` messages and the resulting note list
    is fed directly to :meth:`StyleVAE.encode`.
    """

    import mido  # imported lazily to avoid mandatory dependency

    midi = mido.MidiFile(midi_path)
    notes = [
        msg.note
        for track in midi.tracks
        for msg in track
        if getattr(msg, "type", None) == "note_on" and getattr(msg, "velocity", 0) > 0
    ]
    # ``StyleVAE.encode`` expects a plain list or ``numpy.ndarray`` so convert
    # here based on availability.
    arr = np.array(notes, dtype=float) if USE_NUMPY else [float(n) for n in notes]
    return vae.encode(arr)
