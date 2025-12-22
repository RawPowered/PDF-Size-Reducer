# Local-only environment launcher
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"

if (!(Test-Path $venv)) {
    python -m venv $venv
}

$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
& $py (Join-Path $root "app.py")
