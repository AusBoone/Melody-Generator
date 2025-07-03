"""Tests for the Linux helper script ``scripts/setup_linux.sh``.

This module exercises the script in dry-run mode by stubbing ``apt-get`` and
``python3`` executables. The goal is to ensure Python installation is skipped
when a modern version exists and required packages are still requested.
"""

import os
import subprocess
from pathlib import Path


def test_skip_python_install(tmp_path):
    """Setup script should not install python when version >= 3.8."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "log.txt"

    # Stub apt-get to record invocations for assertions.
    apt_path = bin_dir / "apt-get"
    apt_path.write_text(
        "#!/bin/bash\necho apt-get $@ >> '%s'\n" % log_file
    )
    apt_path.chmod(0o755)

    # Provide python3 stub with modern version and basic venv support.
    py_path = bin_dir / "python3"
    py_path.write_text(
        "#!/bin/bash\n"
        "if [ \"$1\" = --version ]; then echo 'Python 3.9.1'; exit 0; fi\n"
        "if [ \"$1\" = -m ] && [ \"$2\" = venv ]; then mkdir -p $3/bin; exit 0; fi\n"
    )
    py_path.chmod(0o755)

    # Stub pip for dry-run installs.
    pip_path = bin_dir / "pip"
    pip_path.write_text("#!/bin/bash\necho pip $@ >> '%s'\n" % log_file)
    pip_path.chmod(0o755)

    env = os.environ.copy()
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "FORCE_LINUX": "1",
        "DRY_RUN": "1",
    })

    result = subprocess.run(
        ["bash", "scripts/setup_linux.sh"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "apt-get install -y python3 python3-venv" not in result.stdout
    assert "apt-get install -y fluidsynth" in result.stdout
