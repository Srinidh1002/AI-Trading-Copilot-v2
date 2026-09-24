# Canonical Scheduled Task entry point.
#
# This script invokes ONLY tools/preflight_and_start_five_market_paper.py.
# It NEVER starts the supervisor module directly. All safety authority
# (auth freshness, PAPER flags, locks, limiter, per-market certification,
# state, calendar, calibration, provider health) is owned by the preflight.
#
# Requires a fresh FYERS token already written to the canonical .env by
# fyers_daily_auth.py. If the token is stale, the preflight fails closed
# and this script exits non-zero without launching anything.
#
# Never automates the OAuth browser flow.

$ErrorActionPreference = "Stop"
$repo = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-five-market-readiness"
$py   = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-fyers312-venv\Scripts\python.exe"

Set-Location $repo
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $repo "logs\scheduler"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logPath = Join-Path $logDir "scheduler.log"

$stamp = Get-Date -Format o

# Optional: allow partial (index-only) launch when MCX is calibration-held.
# Set to "" (default) for the strict exit-11-on-partial policy.
$extraArgs = @()

$preflight = Join-Path $repo "tools\preflight_and_start_five_market_paper.py"
if (-not (Test-Path $preflight)) {
    "[$stamp] PREFLIGHT_SCRIPT_MISSING path=$preflight" |
        Out-File -Append $logPath -Encoding utf8
    exit 2
}

"[$stamp] INVOKING_PREFLIGHT args=$($extraArgs -join ' ')" |
    Out-File -Append $logPath -Encoding utf8

# Launch the canonical launcher. It owns all gates and (on success) starts
# the supervisor with --markets <ready-list>. On any hold it exits non-zero
# and starts nothing.
& $py $preflight @extraArgs 2>&1 |
    Tee-Object -FilePath $logPath -Append

$rc = $LASTEXITCODE
"[$stamp] PREFLIGHT_EXIT=$rc" | Out-File -Append $logPath -Encoding utf8
exit $rc
