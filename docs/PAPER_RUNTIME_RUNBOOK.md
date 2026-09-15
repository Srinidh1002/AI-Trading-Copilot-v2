# Certified PAPER Runtime Runbook

## Task 9 live PAPER certification launcher

Task 9 production starts only through the canonical bootstrap-first entrypoint:

`services.certification.task9_production_startup_entrypoint`

The operator-facing Task 9 path is:

canonical runtime config
-> one certified provider bundle
-> one startup acquisition
-> A1-A7 proof bundle
-> canonical startup preflight
-> durable approved receipt
-> `bootstrap.launcher_kwargs()`
-> existing Task 9 launcher using the same provider bundle.

The operator must not manually provide startup-preflight IDs, runtime-config
snapshot IDs, runtime-config hashes, approval booleans, broker-submission flags,
or live-execution eligibility.

Task 9 remains PAPER-only:

- `broker_order_submission = false`
- `live_execution_eligible = false`

### Preconditions

- `config.BROKER == PAPER`
- PAPER trading enabled
- live trading disabled
- Task 9 WebSocket/collector evidence healthy
- no competing Task 9 process owns the persistence root
- canonical campaign/run identity selected
- approved capital, risk and policy references selected

### Required policy references

Pass each policy using:

`--policy-reference key=value`

Required keys:

- `canonical_directional`
- `session`
- `risk`
- `contract_selection`
- `lifecycle`
- `counting`
- `failure_disposition`
- `contract_spread`
- `liquidity`
- `minimum_risk_reward`
- `stop_target`
- `portfolio_concurrency`

### One-cycle verification

Use only:

`python -m services.certification.task9_production_startup_entrypoint`

with `--automated-paper`, the canonical runtime/campaign inputs, all approved
policy references, and `--max-cycles 1`.

Use:

`python -m services.certification.task9_production_startup_entrypoint --help`

to display the exact operator arguments before constructing the command.

Do not bypass the bootstrap-first production entrypoint by invoking the
internal Task 9 launcher directly.

### Monday production session

Use the same bootstrap-first module:

`python -m services.certification.task9_production_startup_entrypoint`

with the same canonical campaign/run identity, persistence locations, capital,
risk controls and approved policy references.

Use `--cycle-interval-seconds 60`.

Do not supply `--max-cycles 1` for the continuous production session.

Every restart also uses the bootstrap-first entrypoint. A fresh startup
acquisition and canonical preflight are required before the existing launcher
can resume.

### Persistence and restart

The persistence root remains the durable Task 9 authority.

Do not clear a surviving process lock until the owning process and durable
state have been investigated.

Ctrl+C remains the graceful operator stop mechanism.

### Certification counting

Only actual PAPER CALL/PUT trades that are entered, terminal closed, lifecycle
resolved, reconciled and INCLUDED can increment the NIFTY or SENSEX `/100`
executed-trade target.

WAIT and NO_TRADE remain separately persisted, outcome-evaluated and reported,
but never increment `/100`.

Replay, synthetic, rehearsal, diagnostic, unavailable, failed, duplicate,
open and unreconciled records never increment `/100`.

### Dashboard

The dashboard remains read-only:

`venv\Scripts\streamlit.exe run app.py`

Dashboard refreshes do not acquire provider data, submit orders or increment
Task 9 certification counters.

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
