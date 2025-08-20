<#
.SYNOPSIS
Setup script for Melody-Generator on Windows 10/11.

.DESCRIPTION
Installs Python and supporting libraries using winget if necessary, then
creates a virtual environment in ./venv and installs project dependencies.
Set the environment variable DRY_RUN=1 to print commands without executing
them. Set INSTALL_ML_DEPS=1 to install optional machine learning libraries
(numpy, the CPU build of torch, onnxruntime and numba) used by the sequence
model and style embedding features. ``numpy`` is pinned to versions below 2
to remain compatible with the project's core dependency constraints.
#
.NOTES
Modification summary:
- Pin ``numpy`` to versions below 2 when optionally installing machine
  learning dependencies. The pin avoids conflicts with the project's core
  dependency constraints which currently expect the 1.x series.
#>

$ErrorActionPreference = 'Stop'

function Run-Command($cmd) {
    if ($env:DRY_RUN -eq '1') {
        Write-Host "DRY RUN: $cmd"
    }
    else {
        Invoke-Expression $cmd
    }
}

function Ensure-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $version = (python --version) -replace 'Python ', ''
    $parts = $version.Split('.')
    if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10)) {
            Write-Host "Found Python $version"
            return
        }
        Write-Host "Python $version too old - installing via winget..."
    }
    else {
        Write-Host 'Python not found - installing via winget...'
    }
    Run-Command 'winget install -e --id Python.Python.3'
}

function Install-Package($id) {
    Run-Command "winget install -e --id $id"
}

function main {
    Ensure-Python
    Install-Package 'FluidSynth.FluidSynth'
    Install-Package 'FluidSynth.GeneralMidiSoundFont'

    if (-not (Test-Path 'venv')) {
        Write-Host 'Creating Python virtual environment in ./venv'
        Run-Command 'python -m venv venv'
    }

    if ($env:DRY_RUN -eq '1') {
        Write-Host 'DRY RUN: .\\venv\\Scripts\\Activate.ps1'
        Write-Host 'DRY RUN: pip install --upgrade pip'
        Write-Host 'DRY RUN: pip install -r requirements.txt'
        Write-Host 'DRY RUN: pip install -e .'
        if ($env:INSTALL_ML_DEPS -eq '1') {
            Write-Host 'DRY RUN: pip install "numpy<2"'  # Pin <2 to prevent core dependency conflicts
            Write-Host 'DRY RUN: pip install torch --index-url https://download.pytorch.org/whl/cpu'
            Write-Host 'DRY RUN: pip install onnxruntime'
            Write-Host 'DRY RUN: pip install numba'
        }
    }
    else {
        .\venv\Scripts\Activate.ps1
        Run-Command 'pip install --upgrade pip'
        Run-Command 'pip install -r requirements.txt'
        Run-Command 'pip install -e .'
        if ($env:INSTALL_ML_DEPS -eq '1') {
            Run-Command 'pip install "numpy<2"'  # Pin <2 to prevent core dependency conflicts
            Run-Command 'pip install torch --index-url https://download.pytorch.org/whl/cpu'
            Run-Command 'pip install onnxruntime'
            Run-Command 'pip install numba'
        }
        deactivate
    }
    Write-Host 'Setup complete. Activate with: .\\venv\\Scripts\\Activate.ps1'
}

main
