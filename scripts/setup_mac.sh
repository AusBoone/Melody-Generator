#!/usr/bin/env bash
#----------------------------------------------------------------------
# setup_mac.sh - Environment setup for Melody-Generator on macOS.
#
# This helper installs Homebrew packages and Python dependencies needed
# to run Melody-Generator. It performs version checks so that existing
# installations are reused when possible.
#
# Usage:
#   ./setup_mac.sh
#
# Set the environment variable DRY_RUN=1 to print commands without
# executing them. The FORCE_MAC=1 variable allows running the script on
# non-macOS systems (useful for CI testing). Set INSTALL_ML_DEPS=1 to
# also install optional PyTorch and NumPy packages for the sequence
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

# verify_mac exits unless running on macOS. The FORCE_MAC variable can
# override this to facilitate automated testing on Linux containers.
verify_mac() {
    if [[ "${FORCE_MAC:-0}" == "1" ]]; then
        return
    fi
    if [[ "$(uname -s)" != "Darwin" ]]; then
        echo "This setup script is intended for macOS." >&2
        exit 1
    fi
}

# check_python ensures Python >=3.8 is installed. If python3 is missing or
# too old the function installs a newer version using Homebrew.
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        local version
        version=$(python3 -V 2>&1 | awk '{print $2}')
        local major minor
        IFS=. read -r major minor _ <<<"$version"
        if (( major > 3 || (major == 3 && minor >= 8) )); then
            echo "Found Python $version"
            return
        fi
        echo "Python $version is too old. Updating via Homebrew..."
    else
        echo "Python3 not found. Installing via Homebrew..."
    fi
    run_cmd brew install python
}

# install_brew_pkg installs a Homebrew package only when it is not already
# present to avoid redundant operations.
install_brew_pkg() {
    local pkg=$1
    if ! brew list "$pkg" >/dev/null 2>&1; then
        echo "Installing $pkg via Homebrew..."
        run_cmd brew install "$pkg"
    else
        echo "$pkg already installed"
    fi
}

main() {
    verify_mac

    # Homebrew must be installed; abort if missing
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew is required but was not found." >&2
        echo "Install Homebrew from https://brew.sh/ and re-run this script." >&2
        exit 1
    fi

    check_python
    install_brew_pkg fluid-synth
    install_brew_pkg fluid-soundfont-gm

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
