"""Verify RNG seeding warnings when NumPy is unavailable.

These tests ensure that both the CLI and GUI alert users when NumPy cannot be
seeded, clarifying that determinism may be reduced without the optional
dependency.
"""

from __future__ import annotations

import builtins
import logging

import pytest

from test_cli_random_chords_validation import cli_env as imported_cli_env
from test_cli_gui_integration import load_module

# Re-export the fixture so tests in this module can depend on it directly.
cli_env = imported_cli_env

_real_import = builtins.__import__


def _missing_numpy_import(name: str, *args, **kwargs):
    """Raise ``ImportError`` when importing NumPy to simulate missing package."""
    if name == "numpy":
        raise ImportError("no numpy")
    return _real_import(name, *args, **kwargs)


@pytest.fixture(autouse=True)
def _patch_import(monkeypatch):
    """Patch ``__import__`` so NumPy appears missing during the test."""
    global _real_import
    _real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", _missing_numpy_import)
    yield
    monkeypatch.setattr(builtins, "__import__", _real_import)


def test_cli_seed_logs_warning(cli_env, caplog):
    """CLI helper should warn when NumPy seeding fails."""
    run_cli, _pkg = cli_env
    cli_mod = __import__(run_cli.__module__, fromlist=[''])
    caplog.set_level(logging.WARNING)
    cli_mod._seed_rng(1)
    assert "numpy" in caplog.text.lower()


def test_gui_seed_logs_warning(caplog):
    """GUI helper should warn when NumPy seeding fails."""
    _pkg, gui_mod, _dummy = load_module()
    caplog.set_level(logging.WARNING)
    gui_mod._seed_rng(1)
    assert "numpy" in caplog.text.lower()
