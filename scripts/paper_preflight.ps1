[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$python = Join-Path $repoRoot 'venv\Scripts\python.exe'
$runtimeDir = Join-Path $repoRoot 'data\paper_trading\certified_runtime'

function Fail([string]$message) {
    Write-Error $message
    exit 1
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { Fail 'Project virtual-environment Python was not found.' }

Write-Host "Repository: $repoRoot"
Write-Host "Branch: $(git branch --show-current)"
Write-Host "HEAD: $(git rev-parse --short HEAD)"
Write-Host 'Worktree status:'
git status --short

$requiredNames = @('ANGEL_API_KEY', 'ANGEL_CLIENT_ID', 'ANGEL_PIN', 'ANGEL_TOTP_SECRET')
$dotenvNames = @()
$dotenvPath = Join-Path $repoRoot '.env'
if (Test-Path -LiteralPath $dotenvPath -PathType Leaf) {
    $dotenvNames = Select-String -LiteralPath $dotenvPath -Pattern '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=' | ForEach-Object { $_.Matches[0].Groups[1].Value }
}
$missing = @($requiredNames | Where-Object { -not (Test-Path "Env:$_") -and $_ -notin $dotenvNames })
if ($missing.Count -gt 0) { Fail "Missing required environment variable names: $($missing -join ', ')" }
Write-Host "Required credential variable names present: $($requiredNames -join ', ')"

foreach ($path in @($runtimeDir, (Join-Path $runtimeDir 'logs'))) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $probe = Join-Path $path '.paper_preflight_write_probe'
    try { [System.IO.File]::WriteAllText($probe, 'ok'); Remove-Item -LiteralPath $probe -Force }
    catch { Fail "Runtime directory is not writable: $path" }
}
Write-Host 'Runtime directories are writable.'

$configPath = Join-Path $repoRoot 'config.py'
$requiredSafety = @('BROKER = "PAPER"', 'ENABLE_PAPER_TRADING = True', 'ENABLE_LIVE_TRADING = False')
$configText = Get-Content -LiteralPath $configPath -Raw
foreach ($setting in $requiredSafety) { if ($configText -notmatch [regex]::Escape($setting)) { Fail "Expected safety configuration not found: $setting" } }
Write-Host 'Expected safety: execution_mode=PAPER; live_execution_eligible=false; broker_order_submission=false.'

& $python -m pytest tests\test_apt1_automated_paper_runtime.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'APT focused preflight passed.'
