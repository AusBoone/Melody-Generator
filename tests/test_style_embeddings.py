"""Tests for the style embedding helpers."""

import importlib
import sys
from pathlib import Path

# Ensure the repository root is on ``sys.path`` so the package imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

style = importlib.import_module("melody_generator.style_embeddings")


def test_style_vector_lookup():
    """Known style names should return fixed-length vectors."""
    vec = style.get_style_vector("jazz")
    assert getattr(vec, "shape", (len(vec),))[0] == 3
