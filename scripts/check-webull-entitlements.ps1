[CmdletBinding()]
param(
    [string]$OptionSymbol,
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    if ([string]::IsNullOrWhiteSpace($OptionSymbol)) {
        throw "OptionSymbol is required. Supply an exact listed option symbol from the operator contract catalog."
    }
    # The delegated script uses only the allowlisted GET account/stock/option
    # snapshot probe and prints a redacted report. Do not echo its raw output.
    $rawReport = & $PSScriptRoot/probe-webull.ps1 -OptionSymbol $OptionSymbol 2>$null
    if ($LASTEXITCODE -ne 0) { throw "The read-only Webull capability probe did not complete." }
    $report = $rawReport | ConvertFrom-Json
} else {
    if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) { throw "ReportPath was not found." }
    $report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
}

if ($report.environment -notin @("production", "prod")) { throw "Entitlement checks require a production redacted report." }
if ($null -eq $report.capabilities.stock_snapshot -or $null -eq $report.capabilities.option_snapshot) {
    throw "Report is missing stock_snapshot or option_snapshot capability state."
}

$stockState = [string]$report.capabilities.stock_snapshot.state
$optionState = [string]$report.capabilities.option_snapshot.state
$stockResult = if ($stockState -eq "verified") { "snapshot_verified" } elseif ($stockState -eq "unavailable") { "subscription_or_access_unavailable" } else { "inconclusive" }
$optionResult = if ($optionState -eq "verified") { "snapshot_verified" } elseif ($optionState -eq "unavailable") { "subscription_or_access_unavailable" } else { "inconclusive" }

[pscustomobject]@{
    environment = "production"
    nasdaq_basic_or_totalview = $stockResult
    opra_realtime_nondisplay = $optionResult
    next_required_measurements = @(
        "Confirm the subscribed plan and non-display terms in Webull.",
        "Measure provider event time, receive time, fields, and delays during market hours.",
        "Test reconnect and bounded option-universe cadence before enabling live rules."
    )
} | ConvertTo-Json -Depth 3
