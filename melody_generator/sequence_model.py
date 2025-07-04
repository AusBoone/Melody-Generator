"""Lightweight sequence model placeholder for melodic prediction.

This module provides a minimal LSTM network to demonstrate how a
pretrained model could be integrated. The implementation intentionally
keeps the architecture simple so unit tests run quickly.

In a real system the weights would be trained on a MIDI corpus and
loaded from disk via :func:`load_sequence_model`. The small helper
:func:`predict_next` performs one forward pass to obtain a note index.
"""

from __future__ import annotations

import os
from typing import List, Optional

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - dependency may be missing
    torch = None
    import types

    nn = types.SimpleNamespace(Module=object)


class MelodyLSTM(nn.Module):
    """Tiny LSTM used to predict the next note index."""

    def __init__(self, vocab_size: int, hidden_size: int = 32) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required for MelodyLSTM")
        super().__init__()
        self.embed = nn.Embedding(vocab_size, hidden_size)
        self.lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, vocab_size)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:  # pragma: no cover - simple wrapper
        out = self.embed(seq)
        out, _ = self.lstm(out)
        out = self.fc(out[:, -1])
        return out


def load_sequence_model(path: Optional[str], vocab_size: int) -> MelodyLSTM:
    """Load a pretrained model or create a fresh one when ``path`` is absent."""
    if torch is None:
        raise RuntimeError("PyTorch is required to load the sequence model")

    model = MelodyLSTM(vocab_size)
    if path and os.path.exists(path):
        state = torch.load(path, map_location="cpu")
        model.load_state_dict(state)
    return model


def predict_next(model: MelodyLSTM, history: List[int]) -> int:
    """Return the most likely next index according to ``model``."""
    if torch is None:
        raise RuntimeError("PyTorch is required for predict_next")
    if not history:
        raise ValueError("history must contain at least one index")
    tensor = torch.tensor([history], dtype=torch.long)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)
        return int(torch.argmax(probs, dim=1)[0])


def export_onnx(model: MelodyLSTM, path: str, seq_len: int = 4) -> None:
    """Export ``model`` to ONNX format for inference.

    Parameters
    ----------
    model:
        The LSTM instance to export. Must be on CPU.
    path:
        Destination ``.onnx`` file path.
    seq_len:
        Length of the dummy input sequence used for tracing. Defaults to ``4``.

    Raises
    ------
    RuntimeError
        If PyTorch is unavailable.
    """

    if torch is None:
        raise RuntimeError("PyTorch is required for export_onnx")

    dummy = torch.randint(0, model.embed.num_embeddings, (1, seq_len))
    torch.onnx.export(
        model,
        dummy,
        path,
        input_names=["seq"],
        output_names=["logits"],
        opset_version=12,
    )
