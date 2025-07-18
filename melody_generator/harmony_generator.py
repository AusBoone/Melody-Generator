"""Simple chord progression and harmonic rhythm generator.

This module offers lightweight helpers for constructing a chord
progression and matching harmonic rhythm (duration of each chord).
It intentionally keeps the rules minimal so unit tests can run
without heavy dependencies.

Example
-------
>>> chords, rhythm = generate_progression("C", 4)
>>> chords
['C', 'F', 'G', 'C']
>>> rhythm
[1.0, 1.0, 2.0, 0.5]
"""

from __future__ import annotations

import random
from typing import List, Tuple, Optional
import math
import re

# Importing these lazily within functions avoids circular imports when
# ``HarmonyGenerator`` is pulled into :mod:`melody_generator` during package
# initialisation.

# Common four-chord pop progressions encoded as degrees relative to the key
_DEGREE_PATTERNS = [
    [0, 3, 4, 0],  # I-IV-V-I
    [0, 5, 3, 4],  # I-vi-IV-V
    [0, 3, 0, 4],  # I-IV-I-V
]

# Basic harmonic rhythms measured in beats per chord
_RHYTHM_PATTERNS = [
    [1.0, 1.0, 1.0, 1.0],  # change every beat
    [2.0, 1.0, 1.0],        # half-note then quarters
    [1.0, 2.0, 1.0],        # quarter-note, half-note, quarter
]


def _degree_to_chord(key: str, idx: int) -> str:
    """Return a chord name for ``idx`` scale degree within ``key``.

    Chords default to major/minor triads derived from the key signature.
    When the resulting name is unknown a random fallback from ``CHORDS`` is
    used so the output always contains valid chord symbols.
    """

    from . import SCALE, CHORDS
    notes = SCALE[key]
    is_minor = key.endswith("m")
    if is_minor:
        qualities = ["m", "dim", "", "m", "m", "", ""]
    else:
        qualities = ["", "m", "m", "", "", "m", "dim"]
    note = notes[idx % len(notes)]
    quality = qualities[idx % len(qualities)]
    chord = note + ("" if quality == "dim" else quality)
    if chord not in CHORDS:
        chord = random.choice(list(CHORDS.keys()))
    return chord


def generate_progression(key: str, length: int = 4) -> Tuple[List[str], List[float]]:
    """Create a chord progression and harmonic rhythm for ``key``.

    Parameters
    ----------
    key:
        Musical key used to derive chord qualities. Must exist in ``SCALE``.
    length:
        Number of chords to return. Defaults to ``4``.

    Returns
    -------
    tuple(list[str], list[float])
        ``(chords, rhythm)`` where ``chords`` is a list of chord names and
        ``rhythm`` gives the duration in beats of each chord.

    Raises
    ------
    ValueError
        If ``key`` is unknown or ``length`` is non-positive.
    """

    from . import SCALE

    if key not in SCALE:
        raise ValueError(f"Unknown key '{key}'")
    if length <= 0:
        raise ValueError("length must be positive")

    degrees = random.choice(_DEGREE_PATTERNS)
    chords = [_degree_to_chord(key, d) for d in degrees]
    rhythm = random.choice(_RHYTHM_PATTERNS)
    chords = (chords * (length // len(chords) + 1))[:length]
    rhythm = (rhythm * (length // len(rhythm) + 1))[:length]
    return chords, rhythm

# ------------------------------
# HarmonyGenerator extension
# ------------------------------

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - optional dependency
    torch = None
    import types
    nn = types.SimpleNamespace(Module=object)


class HarmonyBLSTM(nn.Module):
    """Tiny BLSTM predicting chord probabilities per bar."""

    def __init__(self, vocab_size: int, hidden_size: int = 32) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required for HarmonyBLSTM")
        super().__init__()
        self.embed = nn.Embedding(vocab_size, hidden_size)
        self.blstm = nn.LSTM(
            hidden_size,
            hidden_size,
            batch_first=True,
            bidirectional=True,
        )
        self.fc = nn.Linear(hidden_size * 2, vocab_size)

    def forward(self, seq):  # pragma: no cover - small wrapper
        out = self.embed(seq)
        out, _ = self.blstm(out)
        out = self.fc(out[:, -1])
        return out

    def predict(self, history: List[int]) -> List[float]:
        """Return logits for the next chord index."""
        if torch is None:
            raise RuntimeError("PyTorch is required for predict")
        if not history:
            raise ValueError("history must not be empty")
        tensor = torch.tensor([history], dtype=torch.long)
        with torch.no_grad():
            logits = self(tensor)
        return logits.squeeze(0).tolist()


def _downbeat_bars(pattern: List[float], time_signature: Tuple[int, int]) -> int:
    """Return the number of bars covered by ``pattern``."""
    beats_per_bar = time_signature[0] * (4 / time_signature[1])
    total = sum(pattern)
    return int(math.ceil(total / beats_per_bar))


class HarmonyGenerator:
    """Predict chord progressions aligned to the rhythm skeleton."""

    def __init__(self, model: Optional[HarmonyBLSTM] = None) -> None:
        self.model = model

    def _motif_to_degrees(self, key: str, motif: List[str]) -> List[int]:
        from . import SCALE, NOTE_TO_SEMITONE, canonical_key

        key = canonical_key(key)
        scale = SCALE[key]
        degrees: List[int] = []
        for note in motif:
            m = re.fullmatch(r"([A-Ga-g][#b]?)(-?\d+)", note)
            if not m:
                raise ValueError(f"Invalid note: {note}")
            pitch = m.group(1).capitalize()
            pitch = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}.get(
                pitch, pitch
            )
            if pitch in scale:
                degrees.append(scale.index(pitch))
            else:
                root = scale[0]
                diff = (NOTE_TO_SEMITONE[pitch] - NOTE_TO_SEMITONE[root]) % 12
                degrees.append(diff % len(scale))
        return degrees

    def generate(
        self,
        key: str,
        motif: List[str],
        rhythm: List[float],
        *,
        time_signature: Tuple[int, int] = (4, 4),
    ) -> Tuple[List[str], List[float]]:
        """Return chords and durations for ``motif`` within ``key``."""
        if not motif:
            raise ValueError("motif must not be empty")
        if not rhythm:
            raise ValueError("rhythm must not be empty")

        num_bars = _downbeat_bars(rhythm, time_signature)
        beats_per_bar = time_signature[0] * (4 / time_signature[1])

        if self.model is None:
            chords, _ = generate_progression(key, num_bars)
        else:
            history = self._motif_to_degrees(key, motif)
            chords = []
            for _ in range(num_bars):
                logits = self.model.predict(history)
                idx = int(max(range(len(logits)), key=lambda i: logits[i]))
                chords.append(_degree_to_chord(key, idx))
                history.append(idx)

        durations = [beats_per_bar] * num_bars
        return chords, durations
