# Five-Market PAPER Runbook

## Morning start
1. Confirm no stray workers are running:
   Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
     Where-Object { $_.CommandLine -match "run_nifty|run_sensex|mcx_paper_bot" }
2. Run preflight (all three):
   & $py312 f8x_morning_provider.py
   & $py312 f8x_morning_mcx.py
   # state check via PowerShell snippet in 8.3c
3. Start supervisor:
   & $py312 -m services.paper_orchestration.automated_paper_supervisor_v2 --poll-seconds 30

## During session
- Supervisor is the only process to look at.
- Logs: logs/supervisor/supervisor_<DATE>.log
- Per-worker stdout: logs/supervisor/<MARKET>_stdout.log

## After session
- Daily reports: docs/daily_audit/<MARKET>_<DATE>.md
- Counters: data/paper_trades/<market>_experimental.json

## Emergency stop
- Ctrl+C in the supervisor window. It terminates all workers cleanly.
- If a worker refuses to stop, identify by PID:
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
      Where-Object { $_.CommandLine -match "run_nifty|run_sensex|mcx_paper_bot" } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

## Never
- Do not manually edit state files during an epoch.
- Do not manually add or bump counters.
- Do not run two supervisors.
- Do not start workers directly while the supervisor is running.
