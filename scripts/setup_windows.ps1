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

Safeguards:
- Validates that ``winget`` exists before attempting installations to avoid
  partial setup states.
- Applies ``--accept-package-agreements`` and ``--accept-source-agreements`` to
  all ``winget install`` calls so the script can run unattended.
- After installing Python, refreshes the current session to detect the new
  interpreter and instructs the user to restart if it remains unavailable.

Assumptions:
- ``winget`` is installed and accessible in the current shell.

Failure modes:
- Absence of ``winget`` stops the script with a descriptive message.
- If Python remains missing or outdated after installation, users must restart
  their PowerShell session before re-running the script.

.NOTES
Modification summary:
- Validate ``winget`` availability up-front to fail fast when the package
  manager is missing.
- Perform non-interactive ``winget`` installs by accepting agreements.
- Refresh the environment after installing Python and warn if the interpreter
  cannot be located.
- Pin ``numpy`` to versions below 2 when optionally installing machine
  learning dependencies. The pin avoids conflicts with the project's core
  dependency constraints which currently expect the 1.x series.
- Capture command exit codes in ``Run-Command`` and abort on failure to avoid
  silently continuing after errors.
#>

$ErrorActionPreference = 'Stop'

function Ensure-Winget {
    <#
        .SYNOPSIS
        Ensure that the winget package manager is available.

        .DESCRIPTION
        The setup process relies on winget for installing Python and other
        dependencies. If winget cannot be located, the script terminates with
        an explanatory error so users can install it before retrying.
    #>
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Error 'winget is required but was not found. Install winget and re-run this script.'
        exit 1
    }
}

function Run-Command($cmd) {
    <#
        .SYNOPSIS
        Execute a shell command with optional dry-run support.

        .DESCRIPTION
        When ``DRY_RUN`` is set, commands are echoed instead of executed. This
        helps users preview operations without making changes.
        ``Run-Command`` writes the command to the console so the caller can
        observe what would run. After executing a command it inspects
        ``$LASTEXITCODE`` and throws if the command fails, ensuring the overall
        setup process never proceeds in a corrupted state.

        .PARAMETER cmd
        Command string to execute or display.

        .NOTES
        Output is not captured; callers should handle errors from the invoked
        command themselves. Each execution also checks ``$LASTEXITCODE`` so a
        non-zero exit status halts setup immediately, preventing partial or
        inconsistent installs.
    #>
    if ($env:DRY_RUN -eq '1') {
        Write-Host "DRY RUN: $cmd"
    }
    else {
        Invoke-Expression $cmd
        $exitCode = $LASTEXITCODE  # Preserve exit code for explicit failure detection.
        if ($exitCode -ne 0) {
            # Fail fast with a descriptive error to maintain setup integrity.
            throw "Command failed with exit code $exitCode: $cmd"
        }
    }
}

function Ensure-Python {
    <#
        .SYNOPSIS
        Ensure a supported Python interpreter is available.

        .DESCRIPTION
        Checks for ``python`` in the current session and verifies that the
        version is at least 3.10. If missing or outdated, installs Python via
        winget and refreshes the environment so subsequent commands can use the
        new interpreter. The function exits with an error if Python remains
        unavailable after installation, guiding users to restart PowerShell.
    #>
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
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

    Run-Command 'winget install -e --id Python.Python.3 --accept-package-agreements --accept-source-agreements'

    Write-Host 'Refreshing environment to detect newly installed Python'
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Error 'Python installed but not detected. Restart PowerShell and re-run this script.'
        exit 1
    }
    $version = (python --version) -replace 'Python ', ''
    $parts = $version.Split('.')
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) {
        Write-Error "Detected Python $version, but 3.10 or later is required. Restart PowerShell or adjust PATH."
        exit 1
    }
}

function Install-Package($id) {
    <#
        .SYNOPSIS
        Install a package from winget.

        .DESCRIPTION
        Wraps ``winget install`` with the appropriate flags to suppress
        interactive prompts. ``Install-Package`` assumes that ``Ensure-Winget``
        has already verified the availability of winget.

        .PARAMETER id
        The winget package identifier.
    #>
    Run-Command "winget install -e --id $id --accept-package-agreements --accept-source-agreements"
}

function main {
    <#
        .SYNOPSIS
        Entry point orchestrating the Windows setup process.

        .DESCRIPTION
        Validates prerequisites, installs required packages, creates a Python
        virtual environment and installs project dependencies. This function is
        intentionally linear for clarity, and it exits early if critical steps
        fail (e.g., missing winget or Python).
    #>
    Ensure-Winget
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
