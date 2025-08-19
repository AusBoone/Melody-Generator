"""Sequence model helpers used to bias note selection.

The ``SequenceModel`` interface exposes a single method,
``predict_logits``, which returns unnormalised scores for the next
scale degree given the history of previous degrees.  A lightweight LSTM
implementation provides a concrete model, but callers may supply any
object adhering to the interface.  The design deliberately keeps the
architecture simple so that unit tests run quickly and external
dependencies remain optional.

Real applications would train a much larger network on MIDI corpora and
load the resulting weights via :func:`load_sequence_model`.
"""
# Modification Summary:
# - Hardened ``load_sequence_model`` to validate checkpoints and surface
#   clear ``ValueError`` messages when files are missing or malformed.
# - ``torch.load`` now uses the ``weights_only`` flag when supported so
#   extraneous training information is ignored during inference.
# ``load_sequence_model`` now uses ``functools.lru_cache`` so repeated
# requests for the same model avoid costly disk reads.
# - Introduced ``load_genre_sequence_model`` which resolves genre-specific
#   checkpoints and falls back to untrained weights when unavailable.
# - ``load_sequence_model`` ensures models are returned in evaluation mode
#   so stochastic layers like dropout remain inactive during inference.

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Protocol

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - dependency may be missing
    torch = None
    import types

    nn = types.SimpleNamespace(Module=object)

try:  # Optional dependency used when exporting or quantizing models
    from onnxruntime.quantization import QuantType, quantize_dynamic
except Exception:  # pragma: no cover - optional
    quantize_dynamic = None
    QuantType = None


class SequenceModel(Protocol):
    """Abstract interface for predictive sequence models."""

    def predict_logits(self, history: List[int]) -> List[float]:
        """Return raw logits for the next item given ``history``."""


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

    def predict_logits(self, history: List[int]) -> List[float]:
        """Return raw output scores for the next degree.

        Parameters
        ----------
        history:
            Sequence of previous scale degrees represented as integer indices.

        Returns
        -------
        List[float]
            Raw logits for each possible next degree.

        Raises
        ------
        ValueError
            If ``history`` is empty since the model requires context.
        RuntimeError
            If PyTorch is unavailable.
        """

        if torch is None:
            raise RuntimeError("PyTorch is required for predict_logits")
        if not history:
            raise ValueError("history must contain at least one index")
        tensor = torch.tensor([history], dtype=torch.long)
        with torch.no_grad():
            logits = self(tensor)
        return logits.squeeze(0).tolist()


@lru_cache(maxsize=None)
def load_sequence_model(path: Optional[str], vocab_size: int) -> SequenceModel:
    """Return a cached LSTM loaded from ``path`` or an untrained model.

    Parameters
    ----------
    path:
        Optional file system location of the saved model weights.
        ``None`` creates a fresh model instead of loading from disk.
    vocab_size:
        Size of the note vocabulary used when constructing the model.

    Returns
    -------
    SequenceModel
        Loaded model instance configured for evaluation. Repeated calls with
        the same arguments return the cached object to avoid redundant disk
        reads.

    Raises
    ------
    ValueError
        If ``path`` is provided but the checkpoint is missing or malformed.
    RuntimeError
        If PyTorch is unavailable.
    """
    if torch is None:
        raise RuntimeError("PyTorch is required to load the sequence model")

    model = MelodyLSTM(vocab_size)
    if not path:
        # ``None`` indicates that callers want a fresh, untrained model. Even
        # without loaded weights we set the model to evaluation mode so calling
        # code can immediately perform inference without worrying about
        # training-specific behaviour such as dropout.
        model.eval()
        return model

    try:
        if not os.path.exists(path):
            # Surface a consistent error message for nonexistent files.
            raise FileNotFoundError(path)

        # ``weights_only`` is available in PyTorch >= 2.0 and avoids loading
        # optimizer state or other training artefacts.  Older versions simply
        # fall back to the traditional behaviour.
        try:
            state = torch.load(path, weights_only=True, map_location="cpu")
        except TypeError:
            # ``weights_only`` unsupported; fall back to standard loading.
            state = torch.load(path, map_location="cpu")

        if not isinstance(state, dict):
            # ``load_state_dict`` expects a mapping of parameter tensors; any
            # other object is treated as a corrupt checkpoint.
            raise ValueError("checkpoint does not contain a state dict")

        model.load_state_dict(state)
        # ``eval`` switches the module into inference mode, disabling features
        # like dropout and ensuring deterministic behaviour. This call is safe
        # even when the model lacks such layers.
        model.eval()
    except Exception as exc:  # pragma: no cover - exercised via unit tests
        # Rewrap any underlying issue in a ``ValueError`` to provide a clear
        # contract to callers.
        raise ValueError(f"Unable to load model from {path!r}: {exc}") from exc
    return model


@lru_cache(maxsize=None)
def load_genre_sequence_model(
    genre: Optional[str],
    directory: Optional[str],
    vocab_size: int,
) -> SequenceModel:
    """Return a model checkpoint for ``genre`` or a fresh model.

    Parameters
    ----------
    genre:
        Name of the musical genre whose checkpoint should be loaded. ``None``
        or an empty string bypasses loading and returns an untrained model.
    directory:
        Filesystem directory containing genre-specific checkpoints named
        ``{genre}.pt``. When ``None`` the function behaves as though no
        checkpoint exists.
    vocab_size:
        Size of the note vocabulary used when constructing the model.

    Returns
    -------
    SequenceModel
        Loaded model instance. If the checkpoint is unavailable or invalid, an
        untrained model is returned instead.

    Notes
    -----
    ``load_sequence_model`` performs the heavy lifting and raises ``ValueError``
    when loading fails. This wrapper catches those errors so callers can safely
    request a genre that lacks a checkpoint without surrounding try/except
    blocks.
    """

    if not genre or not directory:
        # No specific genre requested; return a fresh model so the caller can
        # still generate output without specialised weights.
        return load_sequence_model(None, vocab_size)

    path = os.path.join(directory, f"{genre}.pt")
    try:
        return load_sequence_model(path, vocab_size)
    except ValueError:
        # Missing or corrupt checkpoint – fall back to an untrained model.
        return load_sequence_model(None, vocab_size)


def predict_next(model: SequenceModel, history: List[int]) -> int:
    """Return the index with the highest score predicted by ``model``."""
    if not history:
        raise ValueError("history must contain at least one index")

    logits = model.predict_logits(history)
    if not logits:
        raise ValueError("model returned no logits")
    return int(max(range(len(logits)), key=lambda i: logits[i]))


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


def quantize_onnx_model(input_path: str, output_path: str) -> None:
    """Apply dynamic 8-bit quantization to an ONNX model.

    Parameters
    ----------
    input_path:
        Path to the floating point ``.onnx`` model.
    output_path:
        Destination for the quantised model.

    Raises
    ------
    RuntimeError
        If ``onnxruntime`` is unavailable.
    """

    if quantize_dynamic is None or QuantType is None:
        raise RuntimeError("onnxruntime is required for quantize_onnx_model")

    quantize_dynamic(
        model_input=input_path,
        model_output=output_path,
        weight_type=QuantType.QInt8,
    )
