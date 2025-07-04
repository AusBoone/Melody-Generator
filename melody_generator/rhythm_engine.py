"""Independent rhythm generation module."""

from __future__ import annotations

import random
from typing import List


BASIC_RHYTHMS = [
    [0.25, 0.25, 0.5],
    [0.5, 0.25, 0.25],
    [0.125, 0.125, 0.25, 0.5],
]


def generate_rhythm(length: int) -> List[float]:
    """Return a random rhythm pattern of ``length`` events."""

    if length <= 0:
        raise ValueError("length must be positive")
    motif = random.choice(BASIC_RHYTHMS)
    pattern = (motif * (length // len(motif) + 1))[:length]
    return pattern
