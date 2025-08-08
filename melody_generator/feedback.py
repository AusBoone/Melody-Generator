"""Quality feedback helpers using Frechet Music Distance (FMD).

This module contains small utilities for evaluating a generated
melody against a reference dataset via Frechet Music Distance.  A
basic hill-climbing loop is provided to refine phrases by randomly
altering notes when the FMD improves.  The implementation purposely
avoids heavy dependencies so the library remains lightweight.

Example
-------
>>> melody = ["C4", "E4", "G4", "C5"]
>>> improved = refine_with_fmd(melody, "C", ["C"], 4)
"""

# Changelog
# ---------
# - Added validation for empty chord progressions in ``refine_with_fmd``.  The
#   previous implementation assumed at least one chord was supplied and would
#   fail with a modulo-by-zero error when the progression was empty.  Raising a
#   ``ValueError`` provides immediate, user-friendly feedback.

from __future__ import annotations

import math
import random
from typing import Iterable, List, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy optional
    np = None

# ---------------------------------------------------------------------------
# Training-set statistics
# ---------------------------------------------------------------------------

# Simple pitch collection from which global mean and variance are derived.
# In a real implementation these would be computed from a large dataset of
# MIDI phrases.  Here we use a small example set so tests run quickly.
_TRAINING_PITCHES = [60, 62, 64, 65, 67, 69, 71, 72]
_TRAIN_MEAN = float(sum(_TRAINING_PITCHES)) / len(_TRAINING_PITCHES)
_TRAIN_VAR = float(
    sum((p - _TRAIN_MEAN) ** 2 for p in _TRAINING_PITCHES) / len(_TRAINING_PITCHES)
)


# Expose the constants for consumers that wish to compute distance manually.
TRAIN_MEAN: float = _TRAIN_MEAN
TRAIN_VAR: float = _TRAIN_VAR


# ---------------------------------------------------------------------------
# Embedding and distance calculations
# ---------------------------------------------------------------------------

def _melody_stats(notes: Iterable[str]) -> Tuple[float, float]:
    """Return ``(mean, variance)`` of MIDI pitches from ``notes``."""

    from . import note_to_midi  # imported here to avoid circular dependency

    if np is not None:
        midi = np.array([note_to_midi(n) for n in notes], dtype=float)
        return float(np.mean(midi)), float(np.var(midi))
    midi = [note_to_midi(n) for n in notes]
    mean = sum(midi) / len(midi)
    var = sum((m - mean) ** 2 for m in midi) / len(midi)
    return float(mean), float(var)


def compute_fmd(
    notes: Iterable[str], mean: float = TRAIN_MEAN, var: float = TRAIN_VAR
) -> float:
    """Return Frechet Music Distance between ``notes`` and training data."""

    m_mean, m_var = _melody_stats(notes)
    return (m_mean - mean) ** 2 + m_var + var - 2 * math.sqrt(m_var * var)


# ---------------------------------------------------------------------------
# Refinement loop
# ---------------------------------------------------------------------------

def refine_with_fmd(
    melody: List[str],
    key: str,
    chord_prog: List[str],
    base_octave: int,
    *,
    max_iter: int = 2,
) -> List[str]:
    """Improve ``melody`` via hill climbing using FMD as the objective.

    Up to five percent of notes are randomly replaced per iteration.  A
    change is kept only if the resulting FMD decreases.  The first and
    last notes remain fixed so cadences and boundaries stay intact.
    """

    if not melody:
        raise ValueError("melody must not be empty")

    if len(melody) < 3:
        # With fewer than three notes there are no interior positions to
        # modify while keeping the first and last notes fixed, so simply
        # return the melody unchanged.
        return melody

    if not chord_prog:
        # The candidate note pool relies on a chord progression.  An empty list
        # would lead to modulo-by-zero errors when selecting chords, so we fail
        # fast with a clear message.
        raise ValueError("chord_prog must contain at least one chord")

    size = max(1, int(len(melody) * 0.05))
    best_score = compute_fmd(melody)

    from . import _candidate_pool  # local import avoids circular dependency

    for _ in range(max_iter):
        positions = random.sample(range(1, len(melody) - 1), size)
        for pos in positions:
            original = melody[pos]
            pool = _candidate_pool(
                key,
                chord_prog[pos % len(chord_prog)],
                base_octave,
                strong=False,
            )
            trial = random.choice(pool)
            melody[pos] = trial
            new_score = compute_fmd(melody)
            if new_score < best_score:
                best_score = new_score
            else:
                melody[pos] = original
    return melody
