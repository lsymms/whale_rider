[CmdletBinding()]
param(
    [string]$OptionSymbol = "AAPL"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
$dependencyDir = Join-Path $env:LOCALAPPDATA "WhaleRider\python-deps"
if (-not (Test-Path -LiteralPath $python)) { throw "Python 3.13 was not found at $python." }
$env:PYTHONPATH = "$root;$dependencyDir" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })
& $python -m backend.adapters.webull.probe_cli --option-symbol $OptionSymbol
if ($LASTEXITCODE -ne 0) { throw "The Webull capability probe failed." }
