<# Five-market live dashboard. Read-only. Safe to run any time. #>

$ErrorActionPreference = "SilentlyContinue"
$repoRoot = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-five-market-readiness"
Set-Location $repoRoot

$today = Get-Date -Format "yyyy-MM-dd"
$now   = Get-Date

Write-Host ""
Write-Host ("=" * 100)
Write-Host ("FIVE-MARKET LIVE DASHBOARD  |  " + $now.ToString("yyyy-MM-dd HH:mm:ss") + " IST")
Write-Host ("=" * 100)

# ---- 1. Worker processes ----
Write-Host ""
Write-Host "[1] WORKER PROCESSES"
Write-Host ("-" * 100)

$procs = @(Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "run_nifty|run_sensex|mcx_paper_bot|automated_paper_supervisor"
    })

if ($procs.Count -eq 0) {
    Write-Host "  (none running)"
} else {
    $rows = @()
    foreach ($p in $procs) {
        $who = "OTHER"
        if     ($p.CommandLine -match "automated_paper_supervisor") { $who = "SUPERVISOR" }
        elseif ($p.CommandLine -match "run_nifty")     { $who = "NIFTY" }
        elseif ($p.CommandLine -match "run_sensex")    { $who = "SENSEX" }
        elseif ($p.CommandLine -match "CRUDEOILM")     { $who = "CRUDEOILM" }
        elseif ($p.CommandLine -match "GOLDM")         { $who = "GOLDM" }
        elseif ($p.CommandLine -match "NATGASMINI")    { $who = "NATGASMINI" }
        $since = ""
        try { $since = ([Management.ManagementDateTimeConverter]::ToDateTime($p.CreationDate)).ToString("HH:mm:ss") } catch {}
        $rows += ,@($who, $p.ProcessId, $p.ParentProcessId, $since)
    }
    $rows = $rows | Sort-Object { $_[0] }, { $_[1] }
    Write-Host ("  {0,-12} {1,-8} {2,-8} {3}" -f "ROLE", "PID", "PARENT", "SINCE")
    Write-Host ("  {0,-12} {1,-8} {2,-8} {3}" -f "----", "---", "------", "-----")
    foreach ($r in $rows) {
        Write-Host ("  {0,-12} {1,-8} {2,-8} {3}" -f $r[0], $r[1], $r[2], $r[3])
    }
    Write-Host ("  total: {0} processes" -f $procs.Count)
}

# ---- 2. State files ----
Write-Host ""
Write-Host "[2] STATE FILES"
Write-Host ("-" * 100)

$markets = @(
    @{ Name = "NIFTY";      File = "data\paper_trades\nifty_experimental.json" }
    @{ Name = "SENSEX";     File = "data\paper_trades\sensex_experimental.json" }
    @{ Name = "CRUDEOILM";  File = "data\paper_trades\mcx_crudeoilm_experimental.json" }
    @{ Name = "GOLDM";      File = "data\paper_trades\mcx_goldm_experimental.json" }
    @{ Name = "NATGASMINI"; File = "data\paper_trades\mcx_natgasmini_experimental.json" }
)

$stateRows = foreach ($m in $markets) {
    $p = Join-Path $repoRoot $m.File
    if (-not (Test-Path $p)) {
        [PSCustomObject]@{ Market=$m.Name; Age="missing"; Active="-"; Counter="-"; LastWrite="-" }
        continue
    }
    $fi   = Get-Item $p
    $age  = [int]((Get-Date) - $fi.LastWriteTime).TotalMinutes
    $j    = Get-Content $p -Raw | ConvertFrom-Json

    # --- both schema shapes ---
    $active = "none"
    if ($j.active_position) {
        $active = "1 position"
    } elseif ($j.active_trades) {
        $n = @($j.active_trades).Count
        if ($n -gt 0) { $active = "$n active" }
    }

    $counter = if ($j.certification_counter -ne $null) { $j.certification_counter }
               elseif ($j.total_trades -ne $null) { $j.total_trades } else { "?" }

    [PSCustomObject]@{
        Market    = $m.Name
        Age       = "$age min ago"
        Active    = $active
        Counter   = $counter
        LastWrite = $fi.LastWriteTime.ToString("HH:mm:ss")
    }
}
$stateRows | Format-Table -AutoSize | Out-String | Write-Host

# ---- 3. Worker stdout ----
Write-Host ""
Write-Host "[3] WORKER STDOUT (last 6 lines each)"
Write-Host ("-" * 100)

foreach ($m in @("NIFTY","SENSEX","CRUDEOILM","GOLDM","NATGASMINI")) {
    $log = "logs\supervisor\${m}_stdout.log"
    Write-Host ""
    Write-Host ("--- $m ---")
    if (Test-Path $log) {
        $fi = Get-Item $log
        $age = [int]((Get-Date) - $fi.LastWriteTime).TotalSeconds
        Write-Host ("  (log updated $age s ago)")
        Get-Content $log -Tail 6 | ForEach-Object { "  $_" }
    } else { Write-Host "  (no log)" }
}

# ---- 4. Stderr ----
Write-Host ""
Write-Host "[4] STDERR (non-empty only)"
Write-Host ("-" * 100)
$anyErr = $false
foreach ($m in @("NIFTY","SENSEX","CRUDEOILM","GOLDM","NATGASMINI")) {
    $err = "logs\supervisor\${m}_stderr.log"
    if (Test-Path $err) {
        $content = Get-Content $err -Tail 6
        if ($content) {
            Write-Host ""
            Write-Host "--- $m ---"
            $content | ForEach-Object { "  $_" }
            $anyErr = $true
        }
    }
}
if (-not $anyErr) { Write-Host "  (all clear)" }

# ---- 5. Supervisor tick ----
Write-Host ""
Write-Host "[5] SUPERVISOR TICK (last 6)"
Write-Host ("-" * 100)
$supLog = "logs\supervisor\supervisor_$today.log"
if (Test-Path $supLog) { Get-Content $supLog -Tail 6 | ForEach-Object { "  $_" } }
else { Write-Host "  (no supervisor log for today)" }

# ---- 6. Counters ----
Write-Host ""
Write-Host "[6] TODAY'S COUNTERS"
Write-Host ("-" * 100)
foreach ($m in @("NIFTY","SENSEX","CRUDEOILM","GOLDM","NATGASMINI")) {
    $log = "logs\supervisor\${m}_stdout.log"
    if (-not (Test-Path $log)) { continue }
    $gaps   = (Select-String -Path $log -Pattern "QUOTE_GAP_STARTED"      | Measure-Object).Count
    $limits = (Select-String -Path $log -Pattern "request limit reached"  | Measure-Object).Count
    $entrs  = (Select-String -Path $log -Pattern "Trade: BUY|Trade: SELL" | Measure-Object).Count
    $closes = (Select-String -Path $log -Pattern "Position Closed"        | Measure-Object).Count
    Write-Host ("  {0,-12}  entries={1,-3}  closes={2,-3}  rate_limits={3,-3}  quote_gaps={4}" -f $m, $entrs, $closes, $limits, $gaps)
}

Write-Host ""
Write-Host ("=" * 100)


