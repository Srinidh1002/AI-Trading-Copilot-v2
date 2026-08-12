# Certified PAPER Runtime Runbook

## Task 9 live PAPER certification launcher

Task 9 is started only with the dedicated two-market launcher. It obtains one
current NIFTY and one current SENSEX handoff from the certified Task 8 default
composition, then passes those exact handoffs to the Task 9 runner. Broker
submission remains disabled; this launcher has no live-broker mode.

### Preconditions

- Activate the repository virtual environment.
- Confirm `config.BROKER == PAPER`, PAPER trading is enabled, and live trading
  is disabled. Startup fails closed otherwise.
- Choose one stable, operator-assigned `official_run_id` for the entire
  certification run, such as `task9-live-20260810-a`. Keep it unchanged for
  every restart using that persistence root.
- Ensure no other Task 9 launcher owns the same persistence root.

### One-cycle verification

Run a single PAPER cycle before the operator session:

```powershell
venv\Scripts\python.exe -m services.certification.task9_live_paper_certification_launcher `
  --automated-paper `
  --official-run-id task9-live-20260810-a `
  --persistence-root data\paper_trading\certified_runtime\task9 `
  --max-cycles 1
```

This is a one-cycle operational verification, not historical/replay credit.
Outside an entry window the existing Task 9 session authority suppresses new
entries; it never manufactures countable records.

### Monday production command

Use the same root and official ID for the intended live PAPER session:

```powershell
venv\Scripts\python.exe -m services.certification.task9_live_paper_certification_launcher `
  --automated-paper `
  --official-run-id task9-live-20260810-a `
  --persistence-root data\paper_trading\certified_runtime\task9 `
  --cycle-interval-seconds 60
```

The existing Task 9 session authority controls pre-open, 09:15 opening,
15:20 new-entry cutoff, continuing active-position monitoring, and 15:40
close. Do not add a second launcher or a second session policy.

### Persistence, restart, and stop handling

`--persistence-root` is the durable Task 9 boundary. It contains:

- `task9-live-paper-run.json` — stable official run identity and start time.
- `task9-live-paper.lock` — exclusive launcher ownership while the process is
  running.
- `task9-cycle-results/` — idempotent runner-cycle receipts.
- Task 9 production stores: `prediction-ledger.json`,
  `prediction-paper-bindings.json`, `prediction-lifecycle-context.json`,
  `prediction-observation-windows.json`, `prediction-lifecycle-outcomes.json`,
  `prediction-lifecycle-reconciliations.json`, `paper-portfolio-policies.json`,
  `p7-trades.json`, and `p8-portfolios.json`.

Restart with the exact same command, root, and `official_run_id`:

```powershell
venv\Scripts\python.exe -m services.certification.task9_live_paper_certification_launcher `
  --automated-paper `
  --official-run-id task9-live-20260810-a `
  --persistence-root data\paper_trading\certified_runtime\task9 `
  --cycle-interval-seconds 60
```

Use Ctrl+C to stop accepting new cycles. It releases the lock only after the
current durable boundary returns and preserves the stores above for restart.
If a process crashes, its lock remains deliberately fail-closed: do not delete
it or start a competing process until an operator has investigated the owning
process and durable state. This is the emergency-halt procedure; there is no
broker or live-order emergency control because no broker submission is
reachable.

### Post-run progress verification

Progress is built only from reconciled, archived daily Task 9 reports; the
launcher does not mutate `/100` counters. After the existing daily-report
authority has archived the session, recover and build its authoritative view:

```powershell
venv\Scripts\python.exe -c "from services.certification.task9_daily_report_index import Task9DailyReportIndex; from services.certification.task9_daily_report_recovery import recover_task9_daily_reports; from services.certification.task9_live_paper_certification_progress_builder import build_task9_live_paper_certification_progress_from_raw; root='data/paper_trading/certified_runtime/task9'; run_id='task9-live-20260810-a'; reports=recover_task9_daily_reports(index=Task9DailyReportIndex(official_run_id=run_id, file_path=root + '/task9_daily_report_index.json'), official_run_id=run_id, archive_root=root + '/certification_reports'); print(build_task9_live_paper_certification_progress_from_raw(reports).to_dict())"
```

Only entered, terminal-closed, reconciled PAPER `CALL`/`PUT` trades increment
the two `/100` targets. Historical, replay, and test records do not count.
`WAIT` and `NO_TRADE` remain separate analytics and never increment `/100`.

### Task 9 dashboard bridge

Start the read-only dashboard in its own process:

```powershell
venv\Scripts\streamlit.exe run app.py
```

The Task 9 launcher atomically writes its latest typed publication to
`data\paper_trading\certified_runtime\task9\dashboard-publication.json`.
The Streamlit process first uses any in-process publication, then recovers that
file after restart. Before the first Task 9 publication it displays the six-page
Task 9.15 shell with explicit not-yet-published states, never the legacy
fallback. After publication it displays the persisted read-only state. A
missing file is expected before the first run; corrupt state fails closed and
preserves the dashboard's last-known-good session view. Dashboard refreshes do
not acquire data, submit orders, mutate progress, or count toward `/100`.

## Legacy certified runtime launcher — not Task 9 /100 authority

`services.paper_orchestration.certified_runtime_launcher` remains an existing
single-primary-market observation workflow. It is explicitly not a Task 9
certification launcher and must not be used for Task 9 `/100` credit.

### Legacy commands

```powershell
venv\Scripts\python.exe -m services.paper_orchestration.certified_runtime_launcher `
  --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
  --automated-paper --max-cycles 1
```

For legacy read-only use, replace `--automated-paper` with `--observe-only`.
`--emergency-halt` keeps legacy monitoring allowed while suppressing legacy new
entries.

## Legacy post-run inspection

```powershell
venv\Scripts\python.exe scripts\summarize_paper_runtime.py `
  --input data\paper_trading\certified_runtime\runtime.jsonl `
  --output reports\paper_observation\runtime_summary.json `
  --text-output reports\paper_observation\runtime_summary.txt `
  --evidence data\paper_trading\certified_runtime\opportunity_orchestration_journal.json `
  --evidence data\paper_trading\certified_runtime\monitoring_orchestration_journal.json
```
# Task 9 external historical-provider blocker

`EXTERNAL_PROVIDER_CLIENT_CODE_QUOTA_STATE` means Angel historical-data access
was rate-limited outside the repository's request controls. While its durable
Task 9 blocker is `ACTIVE`, the normal Task 9 launcher exits before any market
cycle, receipt, count, or historical request. Waiting does not launch or probe
automatically. After `next_probe_not_before`, an operator may run exactly one
explicit recovery probe; success clears the blocker, while another rate limit
keeps it active. Never delete cache, cooldown, or blocker files to force a run.
Continuous mode remains disabled until a recovery probe succeeds and one
supervised Task 9 cycle passes.

Bootstrap the verified 2026-08-10 evidence without a provider call:

```powershell
venv\Scripts\python.exe -m services.certification.task9_external_provider_recovery_probe --persistence-root data\paper_trading\certified_runtime\task9 --official-run-id task9-live-20260810-a --bootstrap-verified-rate-limit-at 2026-08-10T13:04:32.6665721+05:30
```

Run the later explicit recovery probe only after the persisted gate permits it:

```powershell
venv\Scripts\python.exe -m services.certification.task9_external_provider_recovery_probe --persistence-root data\paper_trading\certified_runtime\task9 --official-run-id task9-live-20260810-a
```
