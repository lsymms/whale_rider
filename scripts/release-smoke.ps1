[CmdletBinding()]
param(
    [switch]$RunRegression,
    [switch]$RunWebullProbe
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
    & node scripts/verify-design.cjs
    if ($LASTEXITCODE -ne 0) { throw "Design contract verification failed." }
    & node tests/contract/core-contracts.cjs
    if ($LASTEXITCODE -ne 0) { throw "Standalone core-contract verification failed." }

    if ($RunRegression) {
        & $PSScriptRoot/run-regression.ps1
        if ($LASTEXITCODE -ne 0) { throw "Host-local regression failed." }
    } else {
        Write-Host "SKIP: host-local regression (pass -RunRegression to execute it)."
    }

    if ($RunWebullProbe) {
        # This is the only optional external action: the existing probe is
        # allowlisted read-only and emits a redacted report. It never sends
        # Telegram or submits brokerage requests.
        & $PSScriptRoot/probe-webull.ps1
        if ($LASTEXITCODE -ne 0) { throw "Read-only Webull capability probe failed." }
    } else {
        Write-Host "SKIP: external Webull capability probe (pass -RunWebullProbe to execute it)."
    }
    Write-Host "PASS: release smoke checklist completed."
} finally {
    Pop-Location
}
