# Setup Guide

This guide explains how to get the project running on each supported platform. The helper scripts install Python, create a virtual environment and set up dependencies automatically.

## macOS
Run:
```bash
./scripts/setup_mac.sh
```
The script uses Homebrew to install Python and FluidSynth. A virtual environment is created in `./venv`.

## Linux
Run:
```bash
./scripts/setup_linux.sh
```
This installs APT packages including FluidSynth, then creates a virtual environment.

## Windows 10/11
Run the PowerShell script:
```powershell
./scripts/setup_windows.ps1
```
It uses `winget` to install Python and Fluidsynth before setting up a virtual environment.

After a script completes activate the environment (`source venv/bin/activate` or `./venv/Scripts/Activate.ps1`) and run `pip install -e .` to install the package in editable mode.

For details on the FluidSynth library itself see [README_FLUIDSYNTH.md](README_FLUIDSYNTH.md).
