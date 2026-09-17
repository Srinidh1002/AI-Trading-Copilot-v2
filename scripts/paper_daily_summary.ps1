[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$python = Join-Path $repoRoot 'venv\Scripts\python.exe'
$summary = Join-Path $PSScriptRoot 'summarize_paper_runtime.py'
$runtimeDir = Join-Path $repoRoot 'data\paper_trading\certified_runtime'
$reportDir = Join-Path $repoRoot 'reports\paper_observation'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual-environment Python was not found.' }
if (-not (Test-Path -LiteralPath $summary)) { throw 'Runtime summary utility was not found.' }
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$date = Get-Date -Format 'yyyy-MM-dd'
& $python $summary --input (Join-Path $runtimeDir 'runtime.jsonl') --output (Join-Path $reportDir "paper_runtime_${date}.json") --text-output (Join-Path $reportDir "paper_runtime_${date}.txt") --evidence (Join-Path $runtimeDir 'opportunity_orchestration_journal.json') --evidence (Join-Path $runtimeDir 'monitoring_orchestration_journal.json')
exit $LASTEXITCODE
