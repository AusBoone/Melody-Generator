import os
import subprocess
from pathlib import Path

def test_skip_python_install(tmp_path):
    """Verify setup script does not attempt to install Python when version is sufficient."""
    # Create directory for fake executables
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "log.txt"

    # Stub brew: exit code 1 for 'list' to force installation for other packages
    brew_path = bin_dir / "brew"
    brew_path.write_text(
        "#!/bin/bash\nif [ \"$1\" = list ]; then exit 1; fi\necho brew $@ >> '%s'\n" % log_file
    )
    brew_path.chmod(0o755)

    # Stub python3 with a modern version and minimal venv support
    py_path = bin_dir / "python3"
    py_path.write_text(
        "#!/bin/bash\n"
        "if [ \"$1\" = -V ]; then echo 'Python 3.9.1'; exit 0; fi\n"
        "if [ \"$1\" = -m ] && [ \"$2\" = venv ]; then mkdir -p $3/bin; exit 0; fi\n"
    )
    py_path.chmod(0o755)

    # Stub pip so install commands succeed in dry run
    pip_path = bin_dir / "pip"
    pip_path.write_text("#!/bin/bash\necho pip $@ >> '%s'\n" % log_file)
    pip_path.chmod(0o755)

    env = os.environ.copy()
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "FORCE_MAC": "1",
        "DRY_RUN": "1",
    })

    result = subprocess.run(
        ["bash", "setup_mac.sh"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    # The script should not attempt to install python because version >=3.8
    assert "brew install python" not in result.stdout
    # But it should attempt to install fluid-synth since brew list fails
    assert "brew install fluid-synth" in result.stdout
