[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$python = Join-Path $repoRoot 'venv\Scripts\python.exe'
$runtimeDir = Join-Path $repoRoot 'data\paper_trading\certified_runtime'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual-environment Python was not found.' }
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$logPath = Join-Path $runtimeDir 'paper_canary_stdout.log'

$previousErrorActionPreference = $ErrorActionPreference

try {
    $ErrorActionPreference = 'Continue'

    & $python -m services.paper_orchestration.certified_runtime_launcher `
        --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
        --automated-paper `
        --max-cycles 1 `
        *> $logPath

    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
Write-Host "Launcher exit code: $exitCode"
Write-Host "Preserved launcher output: $logPath"
$runtimeLog = Join-Path $runtimeDir 'runtime.jsonl'
if (Test-Path -LiteralPath $runtimeLog) {
    Get-Content -LiteralPath $runtimeLog | ForEach-Object {
        try {
            $record = $_ | ConvertFrom-Json
            if ($record.event -in @('RUNTIME_STARTING', 'RUNTIME_STOPPED')) {
                [pscustomobject]@{ event = [string]$record.event; occurred_at = [string]$record.occurred_at }
            }
        }
        catch { }
    } | Select-Object -Last 2 | ForEach-Object {
        Write-Host "Runtime evidence: $($_.event) at $($_.occurred_at)"
    }
}

$summary = Join-Path $PSScriptRoot 'summarize_paper_runtime.py'
if (Test-Path -LiteralPath $summary) { & $python $summary --input $runtimeLog --output (Join-Path $runtimeDir 'canary_summary.json') --text-output (Join-Path $runtimeDir 'canary_summary.txt') }
exit $exitCode
