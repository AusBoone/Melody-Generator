"""Train genre-specific sequence models on multi-genre MIDI corpora.

This script provides a minimal training harness capable of fitting either a
Transformer encoder/decoder or a simple variational autoencoder (VAE) on a
set of MIDI files grouped by musical genre. Each subdirectory under a user
supplied ``data_root`` path is treated as a genre and is expected to contain
``.mid`` files. A separate model is trained for each genre and saved as
``{genre}.pt`` in ``checkpoint_dir``. These checkpoints can later be loaded at
runtime via :func:`melody_generator.load_genre_sequence_model`.

Example
-------
Assuming ``~/midi_corpus`` contains ``jazz/`` and ``rock/`` folders with MIDI
files, the following will train lightweight Transformer models and store the
weights beneath ``models/``::

    python scripts/train_multi_genre.py \
        --data-root ~/midi_corpus \
        --genres jazz rock \
        --model transformer \
        --epochs 10 \
        --checkpoint-dir models

Design Notes
------------
The implementation intentionally favours clarity over raw performance so the
core ideas remain accessible. Real-world projects should incorporate richer
preprocessing, larger models and thorough evaluation. Nevertheless this script
serves as a concrete starting point for experimenting with genre-aware models.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Iterable, List

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

try:
    import mido
except Exception as exc:  # pragma: no cover - MIDI parsing optional
    raise RuntimeError("mido is required for training") from exc

# ---------------------------------------------------------------------------
# Utility data structures
# ---------------------------------------------------------------------------


class MidiDataset(Dataset):
    """Convert MIDI note-on messages to pitch indices for model training.

    Parameters
    ----------
    files:
        Iterable of ``Path`` objects pointing to MIDI files.
    vocab:
        Mapping of MIDI pitch to a contiguous index. Only notes present in
        ``vocab`` are retained; others are skipped to keep the implementation
        compact. Real projects may wish to handle unknown pitches differently.
    """

    def __init__(self, files: Iterable[Path], vocab: Dict[int, int]) -> None:
        self.files = list(files)
        self.vocab = vocab

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.files)

    def __getitem__(self, idx: int) -> torch.Tensor:
        midi = mido.MidiFile(self.files[idx])
        notes: List[int] = []
        for track in midi.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    # Only retain pitches present in the vocabulary.
                    if msg.note in self.vocab:
                        notes.append(self.vocab[msg.note])
        if not notes:
            # Provide a minimal guarantee to avoid zero-length tensors.
            notes.append(0)
        return torch.tensor(notes, dtype=torch.long)


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------


class SimpleTransformer(nn.Module):
    """Tiny Transformer encoder/decoder for sequence modelling.

    The model is intentionally small so examples run quickly. It embeds each
    pitch, applies a stack of Transformer encoder layers and predicts the next
    index in the sequence.
    """

    def __init__(self, vocab_size: int, d_model: int = 128, nhead: int = 4, num_layers: int = 2) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(d_model, vocab_size)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:  # pragma: no cover - thin wrapper
        # ``seq``: (T) tensor of indices. We add a batch dimension for the encoder.
        emb = self.embed(seq).unsqueeze(1)
        encoded = self.encoder(emb)
        return self.fc(encoded[-1])


class SimpleVAE(nn.Module):
    """Minimal VAE operating on note index sequences.

    The VAE compresses each sequence into a latent vector and reconstructs the
    next-note distribution. This toy implementation illustrates the concept
    without aiming for high musical fidelity.
    """

    def __init__(self, vocab_size: int, latent_dim: int = 32) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, latent_dim)
        self.encoder = nn.GRU(latent_dim, latent_dim, batch_first=True)
        self.to_mean = nn.Linear(latent_dim, latent_dim)
        self.to_logvar = nn.Linear(latent_dim, latent_dim)
        self.decoder = nn.GRU(latent_dim, latent_dim, batch_first=True)
        self.out = nn.Linear(latent_dim, vocab_size)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:  # pragma: no cover - example
        emb = self.embed(seq).unsqueeze(0)
        _, hidden = self.encoder(emb)
        mean = self.to_mean(hidden[-1])
        logvar = self.to_logvar(hidden[-1])
        std = torch.exp(0.5 * logvar)
        z = mean + torch.randn_like(std) * std
        dec_out, _ = self.decoder(z.unsqueeze(0))
        return self.out(dec_out.squeeze(0))


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------


def build_model(model_type: str, vocab_size: int) -> nn.Module:
    """Return a model instance based on ``model_type``.

    Parameters
    ----------
    model_type:
        Either ``"transformer"`` or ``"vae"``. The comparison is case-insensitive.
    vocab_size:
        Number of unique notes in the dataset.

    Raises
    ------
    ValueError
        If ``model_type`` is not recognised.
    """

    model_type = model_type.lower()
    if model_type == "transformer":
        return SimpleTransformer(vocab_size)
    if model_type == "vae":
        return SimpleVAE(vocab_size)
    raise ValueError(f"Unsupported model type: {model_type}")


def train_one_epoch(model: nn.Module, loader: DataLoader, criterion: nn.Module, optim: torch.optim.Optimizer) -> float:
    """Train ``model`` for a single epoch and return the average loss."""

    model.train()
    total_loss = 0.0
    for seq in loader:
        optim.zero_grad()
        logits = model(seq[0])  # Use first sequence position to predict next
        loss = criterion(logits, seq[0])
        loss.backward()
        optim.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def train_genre_model(
    genre: str,
    data_dir: Path,
    model_type: str,
    epochs: int,
    checkpoint_dir: Path,
    vocab: Dict[int, int],
) -> None:
    """Train a model for ``genre`` and save the resulting checkpoint."""

    files = list(data_dir.glob("*.mid"))
    if not files:
        raise ValueError(f"No MIDI files found for genre '{genre}' in {data_dir}")

    dataset = MidiDataset(files, vocab)
    loader = DataLoader(dataset, batch_size=1, shuffle=True)
    model = build_model(model_type, len(vocab))
    criterion = nn.CrossEntropyLoss()
    optim = torch.optim.Adam(model.parameters(), lr=1e-3)

    for epoch in range(epochs):
        loss = train_one_epoch(model, loader, criterion, optim)
        logging.info("%s epoch %d loss %.4f", genre, epoch + 1, loss)

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), checkpoint_dir / f"{genre}.pt")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Return parsed command line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="Root directory containing genre subfolders with MIDI files")
    parser.add_argument("--genres", nargs="+", help="List of genres to train (each must match a subdirectory name)")
    parser.add_argument("--model", choices=["transformer", "vae"], default="transformer", help="Model architecture to train")
    parser.add_argument("--epochs", type=int, default=5, help="Number of epochs to train each model")
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("models"), help="Output directory for saved checkpoints")
    return parser.parse_args()


def main() -> None:
    """Entry point used when executing the module as a script."""

    args = parse_args()
    if args.epochs <= 0:
        raise ValueError("epochs must be a positive integer")
    # Build a simple vocabulary spanning the full MIDI range. Real projects may
    # derive this from the dataset instead.
    vocab = {midi: idx for idx, midi in enumerate(range(128))}

    for genre in args.genres:
        data_dir = args.data_root / genre
        if not data_dir.exists():
            raise ValueError(f"Genre directory does not exist: {data_dir}")
        train_genre_model(genre, data_dir, args.model, args.epochs, args.checkpoint_dir, vocab)


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
