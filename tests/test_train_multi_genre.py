"""Tests for the ``scripts.train_multi_genre`` training helpers.

These tests focus on the pieces that were previously incomplete:

* ``MidiDataset`` now emits ``(context, target)`` pairs instead of a raw
  sequence, enabling the training loop to compute a well-defined
  ``CrossEntropyLoss``.
* ``train_one_epoch`` consumes those pairs and backpropagates without raising
  shape errors, even when the data loader supplies multi-sample batches.
* ``train_genre_model`` ties the pieces together and persists a checkpoint so
  downstream components can load genre-specific weights.

The module relies on :mod:`mido` at import time, so each test patches in a
lightweight stub that returns deterministic note-on events.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

try:  # pragma: no cover - import guard
    import torch
    from torch.utils.data import DataLoader, Dataset
except Exception:  # pragma: no cover - PyTorch optional
    torch = None  # type: ignore[assignment]
    DataLoader = Dataset = None  # type: ignore[assignment]

if torch is None or not hasattr(torch, "nn") or DataLoader is None:
    pytest.skip("PyTorch is required for training tests", allow_module_level=True)


@pytest.fixture
def training_module(monkeypatch):
    """Return the training module with ``mido`` replaced by a deterministic stub."""

    class _DummyMessage:
        """Simple structure mimicking a MIDI note-on event."""

        def __init__(self, note: int) -> None:
            self.type = "note_on"
            self.velocity = 64
            self.note = note

    class _DummyMidiFile:
        """Stub ``MidiFile`` that yields a short ascending pattern."""

        def __init__(self, path: Path) -> None:  # pragma: no cover - trivial
            # The path is ignored because tests generate temporary files with no
            # actual MIDI data. Only the structure of ``tracks`` matters.
            pattern = [_DummyMessage(60), _DummyMessage(62), _DummyMessage(64)]
            self.tracks = [pattern]

    stub_mido = types.SimpleNamespace(MidiFile=_DummyMidiFile)
    monkeypatch.setitem(sys.modules, "mido", stub_mido)
    # Ensure the module is re-imported with the stub in place.
    sys.modules.pop("scripts.train_multi_genre", None)
    module = importlib.import_module("scripts.train_multi_genre")
    return module


def test_midi_dataset_returns_context_and_target(training_module, tmp_path):
    """Dataset items should expose prefix notes and the next-note target."""

    module = training_module
    midi_path = tmp_path / "example.mid"
    midi_path.write_bytes(b"")  # File contents are ignored by the stub.
    dataset = module.MidiDataset([midi_path], {60: 0, 62: 1, 64: 2})

    context, target = dataset[0]

    # The stub emits [60, 62, 64] which maps to indices [0, 1, 2]. The context
    # should omit the final element, leaving [0, 1], with the target being 2.
    assert context.tolist() == [0, 1]
    assert target.item() == 2


def test_train_one_epoch_updates_parameters(training_module):
    """Running one epoch should perform gradient steps on model parameters."""

    module = training_module

    class _TinyDataset(Dataset):
        """Yield identical context/target pairs for deterministic behaviour."""

        def __len__(self) -> int:  # pragma: no cover - trivial
            return 4

        def __getitem__(self, index: int):  # pragma: no cover - trivial
            context = torch.tensor([0, 1, 2], dtype=torch.long)
            target = torch.tensor(3, dtype=torch.long)
            return context, target

    loader = DataLoader(_TinyDataset(), batch_size=1, shuffle=False)
    model = module.SimpleTransformer(vocab_size=8)
    optimiser = torch.optim.SGD(model.parameters(), lr=0.1)
    criterion = torch.nn.CrossEntropyLoss()

    before = [param.clone() for param in model.parameters()]
    loss = module.train_one_epoch(model, loader, criterion, optimiser)
    after = list(model.parameters())

    assert loss > 0
    # At least one parameter tensor should differ after optimisation.
    assert any(not torch.equal(b, a) for b, a in zip(before, after))


def test_train_one_epoch_supports_minibatches(training_module):
    """Mini-batched loaders should train without triggering shape errors."""

    module = training_module

    class _MiniBatchDataset(Dataset):
        """Return two distinct training pairs to exercise batch collation."""

        def __len__(self) -> int:  # pragma: no cover - trivial size helper
            return 2

        def __getitem__(self, index: int):  # pragma: no cover - deterministic
            base = torch.tensor([index, index + 1, index + 2], dtype=torch.long)
            target = torch.tensor(index + 3, dtype=torch.long)
            return base, target

    loader = DataLoader(_MiniBatchDataset(), batch_size=2, shuffle=False)
    model = module.SimpleTransformer(vocab_size=16)
    optimiser = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = torch.nn.CrossEntropyLoss()

    before = [param.clone() for param in model.parameters()]
    loss = module.train_one_epoch(model, loader, criterion, optimiser)
    after = list(model.parameters())

    assert loss > 0
    assert any(not torch.equal(b, a) for b, a in zip(before, after))
def test_train_genre_model_writes_checkpoint(training_module, tmp_path):
    """High-level training should materialise a genre checkpoint on disk."""

    module = training_module
    data_dir = tmp_path / "jazz"
    data_dir.mkdir()
    # Touch a fake MIDI file so ``MidiDataset`` receives a path to iterate.
    (data_dir / "phrase.mid").write_bytes(b"")

    checkpoint_dir = tmp_path / "models"
    module.train_genre_model(
        genre="jazz",
        data_dir=data_dir,
        model_type="transformer",
        epochs=1,
        checkpoint_dir=checkpoint_dir,
        vocab={60: 0, 62: 1, 64: 2, 65: 3},
    )

    saved_path = checkpoint_dir / "jazz.pt"
    assert saved_path.exists()
    assert saved_path.stat().st_size > 0
