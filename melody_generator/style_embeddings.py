"""Style embedding helpers and lightweight VAE implementation.

Real deployments would train a full MusicVAE model on a large corpus of MIDI
files. To keep the library self-contained this module offers only minimal
utilities: a tiny :class:`StyleVAE` for demonstrations, functions for setting
an active style vector, interpolation helpers and a way to extract a style
embedding from a reference MIDI file.

``load_styles`` allows additional style vectors to be imported from JSON or
YAML files at runtime so experiments can easily extend the built-in presets.
The loader validates that each imported vector shares a common dimension and
will expand the embedding space when longer vectors are supplied. Existing
presets are padded with zeros to match the new dimensionality, while mismatched
dimensions trigger clear ``ValueError`` exceptions.

``STYLE_VECTORS`` is now defined unconditionally for better static analysis and
helper functions return copies rather than references so callers cannot mutate
module-level state by accident. The built-in presets now include ``blues`` and
``chiptune`` so the defaults match the documentation and CLI examples.
"""

# ---------------------------------------------------------------
# Modification Summary
# ---------------------------------------------------------------
# * ``load_styles`` validates dimensionality and pads existing presets when
#   new vectors expand the embedding space, preventing shape errors.
# * Module-wide style state now relies on ``contextvars.ContextVar`` so threads
#   and asyncio tasks each maintain independent style vectors without
#   interference.
# * Added built-in ``blues`` and ``chiptune`` presets so defaults align with
#   ``docs/README_STYLE_WEIGHTS.md`` and the example configuration files.
# ---------------------------------------------------------------

from __future__ import annotations

from contextvars import ContextVar
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
    # Preset vectors cover multiple musical aesthetics so newcomers can hear
    # stylistic differences without crafting their own embeddings immediately.
    STYLE_VECTORS = {
        "baroque": np.array([1.0, 0.0, 0.0], dtype=float),
        "jazz": np.array([0.0, 1.0, 0.0], dtype=float),
        "pop": np.array([0.0, 0.0, 1.0], dtype=float),
        # ``blues`` emphasises expressive bends and chromatic colouration while
        # maintaining a modest hook density to keep the groove grounded.
        "blues": np.array([0.5, 0.4, 0.1], dtype=float),
        # ``chiptune`` leans on bright harmonic colouration with tight hooks to
        # mimic retro game soundtracks where melodic loops are concise.
        "chiptune": np.array([0.1, 0.8, 0.1], dtype=float),
    }
else:
    STYLE_VECTORS = {
        "baroque": [1.0, 0.0, 0.0],
        "jazz": [0.0, 1.0, 0.0],
        "pop": [0.0, 0.0, 1.0],
        "blues": [0.5, 0.4, 0.1],
        "chiptune": [0.1, 0.8, 0.1],
    }

# Track the dimensionality of the embedding space. This value is updated when
# ``load_styles`` imports vectors with additional elements.
STYLE_DIMENSION = len(next(iter(STYLE_VECTORS.values()))) if STYLE_VECTORS else 0

# ``_STYLE_CTX`` holds the active style vector for the current execution
# context. ``ContextVar`` automatically isolates values across threads and
# asynchronous tasks so concurrent melody generation cannot interfere with each
# other's style configuration.
_STYLE_CTX: ContextVar[Optional[Sequence[float]]] = ContextVar("style_ctx", default=None)


def load_styles(path: str) -> None:
    """Merge style vectors from a JSON or YAML file into ``STYLE_VECTORS``.

    The file must contain a mapping from style names to numeric vectors. Vectors
    are converted to either ``numpy.ndarray`` or ``list`` depending on whether
    NumPy is available. Existing entries are replaced if a name already exists.

    Parameters
    ----------
    path:
        Path to a ``.json`` or ``.yaml``/``.yml`` file defining additional
        styles.

    Raises
    ------
    ValueError
        If the file cannot be parsed, does not contain a mapping of vectors or
        supplies vectors whose dimensions are inconsistent or smaller than the
        current preset size.
    RuntimeError
        If a YAML file is supplied but the ``yaml`` package is missing.
    """

    import json
    import os

    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as fh:
        if ext == ".json":
            try:
                data = json.load(fh)
            except Exception as exc:  # pragma: no cover - parse errors
                raise ValueError("invalid JSON style file") from exc
        elif ext in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("PyYAML is required for YAML style files") from exc
            try:
                data = yaml.safe_load(fh)
            except Exception as exc:  # pragma: no cover - parse errors
                raise ValueError("invalid YAML style file") from exc
        else:
            raise ValueError(f"unsupported style file format: {ext}")

    if not isinstance(data, dict):
        raise ValueError("style file must contain a mapping of names to vectors")

    # Determine the current embedding dimensionality so new vectors can be
    # validated. ``STYLE_DIMENSION`` is kept in sync with ``STYLE_VECTORS``.
    global STYLE_DIMENSION
    current_dim = STYLE_DIMENSION if STYLE_DIMENSION else None

    # Convert and validate the incoming vectors in a temporary dictionary so
    # partial updates are avoided when an error occurs. ``new_dim`` tracks the
    # dimensionality declared by the file and ensures all entries match.
    converted: Dict[str, Sequence[float]] = {}
    new_dim: Optional[int] = None
    for name, vec in data.items():
        if not isinstance(vec, (list, tuple)):
            raise ValueError(f"vector for {name!r} must be a sequence")
        values = [float(v) for v in vec]
        size = len(values)
        if new_dim is None:
            new_dim = size
        elif size != new_dim:
            raise ValueError("all vectors in style file must have the same dimension")
        if current_dim is not None and size < current_dim:
            raise ValueError(
                f"vector for {name!r} has dimension {size} but current dimension is {current_dim}"
            )
        converted[name] = (
            np.array(values, dtype=float) if USE_NUMPY else values
        )

    # Expand existing presets when new vectors introduce additional dimensions by
    # padding with zeros. This keeps all vectors aligned for later operations.
    if new_dim is not None:
        if current_dim is None:
            STYLE_DIMENSION = new_dim
        elif new_dim > current_dim:
            for key, vec in list(STYLE_VECTORS.items()):
                if USE_NUMPY:
                    STYLE_VECTORS[key] = np.pad(
                        np.array(vec, dtype=float), (0, new_dim - current_dim)
                    )
                else:
                    STYLE_VECTORS[key] = list(vec) + [0.0] * (new_dim - current_dim)
            STYLE_DIMENSION = new_dim
        elif new_dim < current_dim:
            raise ValueError(
                f"new vectors have dimension {new_dim} but existing presets use {current_dim}"
            )

    # Merge the validated vectors into the module-level presets.
    STYLE_VECTORS.update(converted)


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
    """Store ``vec`` as the active style for the current execution context.

    ``ContextVar`` ensures that each thread or asyncio task maintains its own
    style state. Passing ``None`` clears the style for the current context. The
    vector is copied into a concrete container to prevent external mutations
    from leaking into subsequent generations.
    """

    if vec is None:
        # Resetting to ``None`` isolates the calling context without touching
        # styles stored in other tasks or threads.
        _STYLE_CTX.set(None)
        return
    # Convert to a concrete container so subsequent caller mutations do not
    # affect the stored style.
    _STYLE_CTX.set(
        np.array(list(vec), dtype=float)
        if USE_NUMPY
        else [float(v) for v in vec]
    )


def get_active_style() -> Optional[Sequence[float]]:
    """Return the context-local style vector previously set via :func:`set_style`.

    A copy is returned so callers cannot mutate the stored value. ``None`` is
    returned when no style has been configured in the current context.
    """

    vec = _STYLE_CTX.get()
    if vec is None:
        return None
    return np.array(vec, dtype=float) if USE_NUMPY else list(vec)


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
