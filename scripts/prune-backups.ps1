[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$BackupDir,
    [ValidateRange(1, 3650)] [int]$Keep = 14,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath($BackupDir)
if ($root.StartsWith("\\") -or $root.StartsWith("//")) { throw "Network backup paths are not allowed." }
if (!(Test-Path -LiteralPath $root -PathType Container)) { throw "Backup directory does not exist." }
$items = Get-ChildItem -LiteralPath $root -File | Where-Object { $_.Name -match '^whale-rider-\d{8}T\d{6}Z\.sqlite3$' } | Sort-Object LastWriteTimeUtc -Descending
$expired = @($items | Select-Object -Skip $Keep)
if (!$expired.Count) { Write-Host "No backups exceed retention of $Keep."; exit 0 }
foreach ($item in $expired) {
    $action = if ($Apply) { "Removing explicit backup" } else { "Would remove explicit backup" }
    Write-Host "${action}: $($item.Name)"
    if ($Apply) {
        Remove-Item -LiteralPath $item.FullName -Force
        $hash = "$($item.FullName).sha256"
        if (Test-Path -LiteralPath $hash -PathType Leaf) { Remove-Item -LiteralPath $hash -Force }
    }
}
