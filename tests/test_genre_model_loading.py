"""Tests for genre-specific model selection helpers."""

import importlib
import logging
import sys
from pathlib import Path

import pytest  # noqa: F401 - fixtures are injected by name


# Ensure the package root is importable when tests are executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _reload_module():
    """Reload ``sequence_model`` fresh for each test."""
    return importlib.reload(importlib.import_module("melody_generator.sequence_model"))


def test_existing_genre_loads_checkpoint(tmp_path, monkeypatch):
    """A matching checkpoint path should be passed to ``load_sequence_model``."""
    seq_mod = _reload_module()

    calls = []

    def fake_loader(path, vocab):
        calls.append(path)
        return object()

    monkeypatch.setattr(seq_mod, "load_sequence_model", fake_loader)
    (tmp_path / "jazz.pt").write_bytes(b"dummy")

    result = seq_mod.load_genre_sequence_model("jazz", str(tmp_path), 8)
    assert result is not None
    assert calls == [str(tmp_path / "jazz.pt")]


def test_missing_genre_falls_back(tmp_path, monkeypatch, caplog):
    """Fallback should occur and warn when the checkpoint is unavailable."""
    seq_mod = _reload_module()

    calls: list[str | None] = []

    def fake_loader(path, vocab):
        calls.append(path)
        if path is not None:
            raise ValueError("missing")
        return "default"

    monkeypatch.setattr(seq_mod, "load_sequence_model", fake_loader)

    with caplog.at_level(logging.WARNING, logger=seq_mod.__name__):
        result = seq_mod.load_genre_sequence_model("rock", str(tmp_path), 8)

    # ``fake_loader`` should first be called with the checkpoint path then ``None``.
    assert calls == [str(tmp_path / "rock.pt"), None]
    assert result == "default"
    # The warning message should mention the missing checkpoint path.
    assert str(tmp_path / "rock.pt") in caplog.text
