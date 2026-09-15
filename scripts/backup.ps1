[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$RuntimeDir,
    [Parameter(Mandatory)] [string]$BackupDir
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) { throw "Project virtual environment Python was not found." }
$runtime = [IO.Path]::GetFullPath($RuntimeDir)
$backupRoot = [IO.Path]::GetFullPath($BackupDir)
$database = Join-Path $runtime "whale-rider.sqlite3"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$target = Join-Path $backupRoot "whale-rider-$stamp.sqlite3"

& $python (Join-Path $PSScriptRoot "sqlite_snapshot.py") backup --source $database --destination $target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
