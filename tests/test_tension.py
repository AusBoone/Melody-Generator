"""Unit tests for tension weighting helpers."""

import importlib
import sys
from pathlib import Path

import pytest

# Ensure project root on path for reliable imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

tension = importlib.import_module("melody_generator.tension")
np = tension.np


def test_apply_tension_weights_numpy():
    """Vectorized multiplication should be used when numpy is available."""
    # When numpy is present ``apply_tension_weights`` should perform a
    # vectorised multiply for efficiency. This test ensures the output matches
    # the manual computation using numpy directly.
    if np is None:
        pytest.skip("numpy not available")

    weights = np.array([1.0, 2.0])
    tensions = [0.2, 0.7]
    result = tension.apply_tension_weights(weights, tensions, 0.5)
    expected = weights * np.array([1 / (1 + abs(t - 0.5)) for t in tensions])
    assert pytest.approx(result.tolist()) == expected.tolist()


def test_apply_tension_weights_list():
    """List inputs should return a new list with adjusted weights."""
    weights = [1.0, 2.0]
    tensions = [0.2, 0.7]
    result = tension.apply_tension_weights(weights, tensions, 0.5)
    expected = [w * (1 / (1 + abs(t - 0.5))) for w, t in zip(weights, tensions)]
    assert result == expected
    assert isinstance(result, list)


def test_apply_tension_weights_tuple():
    """Tuple inputs should fall back to list processing."""
    weights = (1.0, 2.0)
    tensions = [0.2, 0.7]
    result = tension.apply_tension_weights(weights, tensions, 0.5)
    expected = [w * (1 / (1 + abs(t - 0.5))) for w, t in zip(weights, tensions)]
    assert result == expected
    assert isinstance(result, list)


def test_apply_tension_weights_no_numpy(monkeypatch):
    """Fallback path should operate when numpy cannot be imported."""
    # By removing ``numpy`` from ``sys.modules`` and reloading the module we
    # simulate running on a system without the dependency. The helper should
    # gracefully fall back to Python lists without raising errors.
    monkeypatch.setitem(sys.modules, "numpy", None)
    tension_no_np = importlib.reload(importlib.import_module("melody_generator.tension"))

    weights = [1.0, 2.0]
    tensions = [0.2, 0.7]
    result = tension_no_np.apply_tension_weights(weights, tensions, 0.5)
    expected = [w * (1 / (1 + abs(t - 0.5))) for w, t in zip(weights, tensions)]
    assert result == expected

    # Reload original module so other tests retain numpy support
    importlib.reload(tension)


def test_apply_tension_weights_length_mismatch():
    """Length mismatches should raise ``ValueError`` instead of truncating."""

    weights = [1.0, 2.0, 3.0]
    tensions = [0.4, 0.6]

    with pytest.raises(ValueError):
        tension.apply_tension_weights(weights, tensions, 0.5)


def test_apply_tension_weights_empty_inputs():
    """Empty weight collections should raise an informative ``ValueError``."""

    with pytest.raises(ValueError):
        tension.apply_tension_weights([], [], 0.5)

