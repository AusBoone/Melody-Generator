"""Tests for safeguards in ``scripts/setup_windows.ps1``.

These tests read the Windows setup script to confirm that key safeguards such as
winget availability checks and non-interactive installation flags remain in
place. The script itself cannot be executed in this environment, so we inspect
its text to verify expected behaviors.
"""

from __future__ import annotations

import pathlib

# Path to the Windows setup script relative to the repository root.
SCRIPT_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "setup_windows.ps1"


def test_winget_presence_check() -> None:
    """Ensure the script verifies that ``winget`` is installed before continuing."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "Get-Command winget" in content
    assert "winget is required" in content


def test_winget_accepts_agreements() -> None:
    """All ``winget install`` commands should accept agreements automatically."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "--accept-package-agreements --accept-source-agreements" in content


def test_python_refresh() -> None:
    """``Get-Command python`` should appear at least twice to refresh the environment."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert content.count("Get-Command python") >= 2
