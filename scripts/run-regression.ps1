[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [switch]$KeepFrontendMirror
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$hostRoot = Join-Path $env:LOCALAPPDATA "WhaleRider\regression"
$pythonDeps = Join-Path $hostRoot "python-deps"
$frontendMirror = Join-Path $hostRoot "frontend"
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.12+ was not found at $python. Set up host-local Python before running regression."
}
New-Item -ItemType Directory -Force -Path $hostRoot | Out-Null

if (-not $SkipDependencyInstall -or -not (Test-Path -LiteralPath (Join-Path $pythonDeps "fastapi"))) {
    New-Item -ItemType Directory -Force -Path $pythonDeps | Out-Null
    & $python -m pip install --disable-pip-version-check --target $pythonDeps -r (Join-Path $repoRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Host-local Python dependency installation failed." }
}

# npm/rollup can fail when native modules run from an SMB-mapped workspace. Mirror
# only source and lockfiles to the host; node_modules and dist are always local.
if (Test-Path -LiteralPath $frontendMirror) { Remove-Item -LiteralPath $frontendMirror -Recurse -Force }
New-Item -ItemType Directory -Force -Path $frontendMirror | Out-Null
$frontendSource = Join-Path $repoRoot "frontend"
# Invoke directly so paths containing spaces remain separate process arguments.
& robocopy.exe $frontendSource $frontendMirror /E /XD node_modules dist /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -gt 7) { throw "Frontend mirror failed with robocopy exit code $LASTEXITCODE." }

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npm) { throw "npm.cmd was not found. Install Node.js 20+." }
Push-Location $frontendMirror
try {
    & $npm.Source ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    & $npm.Source test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
    & $npm.Source run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}

$env:PYTHONPATH = "$repoRoot;$pythonDeps" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })
Push-Location $repoRoot
try {
    & $python -m pytest tests/unit tests/replay tests/e2e -q
    if ($LASTEXITCODE -ne 0) { throw "Python regression tests failed." }
    & node scripts/verify-design.cjs
    if ($LASTEXITCODE -ne 0) { throw "Design verification failed." }
    & node tests/contract/core-contracts.cjs
    if ($LASTEXITCODE -ne 0) { throw "Standalone contract validation failed." }
} finally {
    Pop-Location
    if (-not $KeepFrontendMirror -and (Test-Path -LiteralPath $frontendMirror)) {
        Remove-Item -LiteralPath $frontendMirror -Recurse -Force
    }
}
Write-Host "PASS: host-local regression completed."
