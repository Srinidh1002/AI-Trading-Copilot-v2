[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$python = Join-Path $repoRoot 'venv\Scripts\python.exe'
$runtimeDir = Join-Path $repoRoot 'data\paper_trading\certified_runtime'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual-environment Python was not found.' }
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$logPath = Join-Path $runtimeDir 'paper_run_5_stdout.log'

& $python -m services.paper_orchestration.certified_runtime_launcher --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher --automated-paper --max-cycles 5 *> $logPath
$exitCode = $LASTEXITCODE
Write-Host "Launcher exit code: $exitCode; output: $logPath"
$summary = Join-Path $PSScriptRoot 'summarize_paper_runtime.py'
if (Test-Path -LiteralPath $summary) { & $python $summary --input (Join-Path $runtimeDir 'runtime.jsonl') --output (Join-Path $runtimeDir 'run_5_summary.json') --text-output (Join-Path $runtimeDir 'run_5_summary.txt') }
exit $exitCode
