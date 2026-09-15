[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$RuntimeDir,
    [Parameter(Mandatory)] [string]$BackupFile,
    [Parameter(Mandatory)] [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) { throw "Project virtual environment Python was not found." }
$runtime = [IO.Path]::GetFullPath($RuntimeDir)
$backup = [IO.Path]::GetFullPath($BackupFile)
$database = Join-Path $runtime "whale-rider.sqlite3"

& $python (Join-Path $PSScriptRoot "sqlite_snapshot.py") restore --source $backup --destination $database --force
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
