"""Tests for the Windows helper script ``scripts/setup_windows.ps1``.

This module runs the PowerShell setup script in dry-run mode. It stubs
``winget`` and ``python`` so the commands can execute on Linux without
actually installing anything. The goal is to verify that the script
skips the Python installation when the existing version is modern and
still attempts to install FluidSynth packages.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_skip_python_install(tmp_path):
    """Setup script should not install python when version >= 3.8."""
    if shutil.which("pwsh") is None:
        pytest.skip("pwsh not installed")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "log.txt"

    # Stub winget to capture invocations for assertions
    winget_path = bin_dir / "winget"
    winget_path.write_text(
        "#!/bin/bash\necho winget $@ >> '%s'\n" % log_file
    )
    winget_path.chmod(0o755)

    # Stub python with a modern version and minimal venv support
    py_path = bin_dir / "python"
    py_path.write_text(
        "#!/bin/bash\n"
        "if [ \"$1\" = --version ]; then echo 'Python 3.9.1'; exit 0; fi\n"
        "if [ \"$1\" = -m ] && [ \"$2\" = venv ]; then mkdir -p $3/bin; exit 0; fi\n"
    )
    py_path.chmod(0o755)

    env = os.environ.copy()
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "DRY_RUN": "1",
    })

    result = subprocess.run(
        ["pwsh", "-File", "scripts/setup_windows.ps1"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "winget install -e --id Python.Python.3" not in result.stdout
    assert "winget install -e --id FluidSynth.FluidSynth" in result.stdout
