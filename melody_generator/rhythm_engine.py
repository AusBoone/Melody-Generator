"""Independent rhythm generation module.

This file exposes a small :class:`RhythmGenerator` class implementing a
probabilistic grammar over common note lengths.  Melody generation functions
use this engine to create onset patterns before assigning pitches.  Decoupling
rhythm from pitch mirrors a typical composing workflow where the groove is
established first and notes are layered on afterwards.

The default transitions form a first-order Markov process so that each duration
suggests a few likely successors.  ``generate_rhythm`` simply proxies to a
module-level ``RhythmGenerator`` instance for convenience.
"""

from __future__ import annotations

import random
from typing import Dict, List


BASIC_RHYTHMS = [
    [0.25, 0.25, 0.5],
    [0.5, 0.25, 0.25],
    [0.125, 0.125, 0.25, 0.5],
]


class RhythmGenerator:
    """Generate rhythmic patterns using a simple Markov grammar."""

    def __init__(
        self,
        transitions: Dict[float, Dict[float, float]] | None = None,
        *,
        start: float | None = None,
    ) -> None:
        """Create a new generator with optional custom transitions.

        Parameters
        ----------
        transitions:
            Mapping ``current_duration -> {next_duration: probability}``. The
            probabilities for each next duration do not need to sum to one as
            they are normalised during generation.  When ``None`` a small
            built-in set of patterns is used.
        start:
            Optional initial duration.  When ``None`` a random one is chosen
            from the keys of ``transitions`` at runtime.
        """

        self.transitions = transitions or {
            0.25: {0.25: 0.4, 0.5: 0.3, 0.125: 0.3},
            0.5: {0.25: 0.6, 0.5: 0.4},
            0.125: {0.125: 0.5, 0.25: 0.5},
        }
        self.start = start

    def generate(self, length: int) -> List[float]:
        """Return a rhythm pattern ``length`` events long."""

        if length <= 0:
            raise ValueError("length must be positive")
        current = self.start
        if current is None:
            current = random.choice(list(self.transitions))
        pattern = [current]
        while len(pattern) < length:
            choices = self.transitions.get(current)
            if not choices:
                choices = {d: 1.0 for d in self.transitions}
            durations = list(choices)
            weights = list(choices.values())
            current = random.choices(durations, weights=weights, k=1)[0]
            pattern.append(current)
        return pattern[:length]


_DEFAULT_GENERATOR = RhythmGenerator()


def generate_rhythm(length: int) -> List[float]:
    """Return a random rhythm pattern of ``length`` events."""

    return _DEFAULT_GENERATOR.generate(length)
