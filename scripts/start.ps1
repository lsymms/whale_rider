[CmdletBinding()]
param(
    [int]$Port = 8787,
    [string]$RuntimeDir = "",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.13 was not found at $python. Install Python 3.12+ and update this launcher."
}

$localRoot = Join-Path $env:LOCALAPPDATA "WhaleRider"
$dependencyDir = Join-Path $localRoot "python-deps"
if (-not $SkipDependencyInstall -and -not (Test-Path -LiteralPath (Join-Path $dependencyDir "fastapi"))) {
    New-Item -ItemType Directory -Force -Path $dependencyDir | Out-Null
    & $python -m pip install --disable-pip-version-check --target $dependencyDir -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = $localRoot }
$env:APP_HOST = "127.0.0.1"
$env:APP_PORT = "$Port"
$env:APP_RUNTIME_DIR = $RuntimeDir
$env:PYTHONPATH = "$root;$dependencyDir" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })

& $python -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
