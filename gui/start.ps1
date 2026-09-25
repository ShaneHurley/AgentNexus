# Start the shared agent dashboard (Windows PowerShell)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-PyVersion([string]$Flag) {
  try {
    & py $Flag -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  foreach ($ver in @("-3.13", "-3.12", "-3.11", "-3.10", "-3")) {
    if (Test-PyVersion $ver) {
      & py $ver start.py @args
      exit $LASTEXITCODE
    }
  }
}

if (Get-Command python -ErrorAction SilentlyContinue) {
  & python start.py @args
  exit $LASTEXITCODE
}

Write-Error "Python 3.10+ not found. Install from https://www.python.org/downloads/"
