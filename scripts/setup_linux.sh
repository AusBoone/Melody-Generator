#!/usr/bin/env bash
#----------------------------------------------------------------------
# setup_linux.sh - Environment setup for Melody-Generator on Linux.
#
# This helper installs APT packages and Python dependencies required to
# run Melody-Generator. It checks for an existing Python 3 installation
# and only installs a new version when the current one is older than 3.8.
# A Python virtual environment is created under ./venv.
#
# Usage:
#   ./setup_linux.sh
#
# Set the environment variable DRY_RUN=1 to print commands without
# executing them. This is useful for verifying the commands on systems
# where sudo privileges might be restricted. Set INSTALL_ML_DEPS=1 to also
# install optional PyTorch and NumPy dependencies used by the sequence
# model features.
#----------------------------------------------------------------------
set -euo pipefail

# run_cmd executes a command or prints it when DRY_RUN is enabled.
run_cmd() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "DRY RUN: $*"
    else
        "$@"
    fi
}

# verify_linux exits unless running on Linux. The FORCE_LINUX variable
# can override this to facilitate automated testing on other systems.
verify_linux() {
    if [[ "${FORCE_LINUX:-0}" == "1" ]]; then
        return
    fi
    if [[ "$(uname -s)" != "Linux" ]]; then
        echo "This setup script is intended for Linux." >&2
        exit 1
    fi
}

# check_python ensures Python >=3.8 is installed. If python3 is missing or
# too old the function installs a newer version using apt-get.
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local version
        version=$(python3 --version 2>&1 | awk '{print $2}')
        local major minor
        IFS=. read -r major minor _ <<<"$version"
        if (( major > 3 || (major == 3 && minor >= 8) )); then
            echo "Found Python $version"
            return
        fi
        echo "Python $version is too old. Installing via apt-get..."
    else
        echo "Python3 not found. Installing via apt-get..."
    fi
    run_cmd sudo apt-get update
    run_cmd sudo apt-get install -y python3 python3-venv
}

# install_pkg installs an APT package unconditionally. The command is
# wrapped with run_cmd so that DRY_RUN will skip execution.
install_pkg() {
    local pkg=$1
    echo "Installing $pkg via apt-get..."
    run_cmd sudo apt-get install -y "$pkg"
}

main() {
    verify_linux

    check_python
    install_pkg fluidsynth
    install_pkg fluid-soundfont-gm
    install_pkg python3-tk
    install_pkg libfluidsynth-dev

    if [[ ! -d venv ]]; then
        echo "Creating Python virtual environment in ./venv"
        run_cmd python3 -m venv venv
    fi

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "DRY RUN: source venv/bin/activate"
        echo "DRY RUN: pip install --upgrade pip"
        echo "DRY RUN: pip install -r requirements.txt"
        echo "DRY RUN: pip install -e ."
        if [[ "${INSTALL_ML_DEPS:-0}" == "1" ]]; then
            echo "DRY RUN: pip install numpy"
            echo "DRY RUN: pip install torch --index-url https://download.pytorch.org/whl/cpu"
        fi
    else
        # shellcheck source=/dev/null
        source venv/bin/activate
        run_cmd pip install --upgrade pip
        run_cmd pip install -r requirements.txt
        run_cmd pip install -e .
        if [[ "${INSTALL_ML_DEPS:-0}" == "1" ]]; then
            run_cmd pip install numpy
            run_cmd pip install torch --index-url https://download.pytorch.org/whl/cpu
        fi
        deactivate
    fi

    echo "Setup complete. Activate with: source venv/bin/activate"
}

main "$@"
