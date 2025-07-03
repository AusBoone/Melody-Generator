<#
.SYNOPSIS
Setup script for Melody-Generator on Windows 10/11.

.DESCRIPTION
Installs Python and supporting libraries using winget if necessary, then
creates a virtual environment in ./venv and installs project dependencies.
Set the environment variable DRY_RUN=1 to print commands without executing
them.
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
        if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 8)) {
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
    }
    else {
        .\venv\Scripts\Activate.ps1
        Run-Command 'pip install --upgrade pip'
        Run-Command 'pip install -r requirements.txt'
        Run-Command 'pip install -e .'
        deactivate
    }
    Write-Host 'Setup complete. Activate with: .\\venv\\Scripts\\Activate.ps1'
}

main
