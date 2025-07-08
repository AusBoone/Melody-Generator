"""Data augmentation and transfer learning helpers.

This module provides functions for augmenting MIDI note sequences and
fine-tuning ``SequenceModel`` instances.  It is intentionally lightweight so
unit tests run quickly.  Real applications would pre-process the GigaMIDI
corpus or a similar dataset and train much larger networks offline.

Example
-------
>>> seq = [60, 62, 64, 65]
>>> transpose_sequence(seq, 2)
[62, 64, 66, 67]
"""

from __future__ import annotations

import random
from typing import Iterable, List

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - optional dependency
    torch = None
    nn = None  # type: ignore


def transpose_sequence(notes: Iterable[int], semitones: int) -> List[int]:
    """Return ``notes`` shifted by ``semitones``.

    Parameters
    ----------
    notes:
        Sequence of MIDI pitches.
    semitones:
        Number of half steps to shift. Positive values transpose up.

    Returns
    -------
    List[int]
        Transposed note sequence.
    """

    return [max(0, min(127, n + semitones)) for n in notes]


def invert_sequence(notes: Iterable[int], pivot: int) -> List[int]:
    """Return the inversion of ``notes`` around ``pivot``.

    ``pivot`` typically represents the tonic. Each note ``n`` is mapped to
    ``2 * pivot - n``.  Values are clamped to the valid MIDI range.
    """

    return [max(0, min(127, 2 * pivot - n)) for n in notes]


def perturb_rhythm(pattern: Iterable[float], jitter: float = 0.05) -> List[float]:
    """Return ``pattern`` with each duration jittered by up to ``jitter``.

    Durations never drop below ``0.05`` to avoid zero-length notes.
    """

    if jitter < 0:
        raise ValueError("jitter must be non-negative")
    perturbed = []
    for dur in pattern:
        if dur <= 0:
            raise ValueError("pattern durations must be positive")
        offset = random.uniform(-jitter, jitter)
        perturbed.append(max(0.05, dur + offset))
    return perturbed


def augment_sequences(
    sequences: Iterable[Iterable[int]],
    *,
    transpose_range: Iterable[int] = range(-2, 3),
    invert: bool = True,
) -> List[List[int]]:
    """Return augmented copies of ``sequences``.

    Each sequence is duplicated for every value in ``transpose_range``. When
    ``invert`` is ``True`` the inverted form is appended alongside each
    transposition using the sequence's first note as the pivot.

    Parameters
    ----------
    sequences:
        Iterable of pitch sequences to augment. Must not be empty.
    transpose_range:
        Collection of semitone offsets applied to each sequence. Defaults to
        ``range(-2, 3)`` yielding five transpositions.
    invert:
        When ``True`` append an inverted version for each transposition.

    Returns
    -------
    list[list[int]]
        Augmented pitch sequences.

    Raises
    ------
    ValueError
        If ``sequences`` is empty.
    """
    sequences = list(sequences)
    if not sequences:
        raise ValueError("sequences must not be empty")

    augmented: List[List[int]] = []
    for seq in sequences:
        # Operate on a list copy so repeated transpositions do not mutate the
        # caller's sequence object.
        seq = list(seq)
        for t in transpose_range:
            # Add a transposed version for each semitone offset.
            augmented.append(transpose_sequence(seq, t))
            if invert:
                # Optionally include the inverted form using the first note as
                # the pivot so melodic contour is mirrored.
                augmented.append(invert_sequence(seq, seq[0]))
    return augmented


def fine_tune_model(
    model: "nn.Module",
    sequences: List[List[int]],
    *,
    epochs: int = 1,
    lr: float = 0.001,
) -> "nn.Module":
    """Fine-tune ``model`` on ``sequences`` using teacher forcing.

    ``sequences`` should already be converted to pitch indices within the
    model's vocabulary.  Sequences shorter than two notes are skipped.
    """

    if torch is None:
        raise RuntimeError("PyTorch is required for fine_tune_model")
    if not sequences:
        raise ValueError("sequences must not be empty")

    optimiser = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    for _ in range(epochs):
        # Iterate over the dataset one sequence at a time. Short sequences are
        # skipped because the model requires at least one input and one target
        # token for teacher forcing.
        for seq in sequences:
            if len(seq) < 2:
                continue
            # Prepare input/output tensors on CPU for a single training step.
            data = torch.tensor([seq[:-1]], dtype=torch.long)
            target = torch.tensor(seq[1:], dtype=torch.long)
            optimiser.zero_grad()
            logits = model(data)
            loss = criterion(logits, target)
            loss.backward()
            optimiser.step()
    return model
