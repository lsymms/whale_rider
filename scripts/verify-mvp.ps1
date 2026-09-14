[CmdletBinding()]
param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

Push-Location $repoRoot
try {
    & $python -m pytest tests/e2e -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($Full) {
        & $python -m pytest tests/unit -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        & node scripts/verify-design.cjs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & node tests/contract/core-contracts.cjs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
        Write-Warning "Node.js was not found; skipped design and standalone contract checks."
    }
    Write-Host "PASS: local MVP verification completed."
} finally {
    Pop-Location
}
