# Certified PAPER Runtime Runbook

## Preconditions

- Activate the repository virtual environment.
- Confirm `config.BROKER == PAPER`, PAPER trading enabled, and live trading
  disabled. The certified composition rejects other combinations.
- Start with the standard NIFTY primary configuration. SENSEX is supported as
  an explicit primary setting in composition code, but the stock CLI factory
  defaults to NIFTY and does not run both markets in one cycle.
- Keep broker order submission disabled. The runtime is not a live order tool.

## Launch commands

One cycle:

```powershell
venv\Scripts\python.exe -m services.paper_orchestration.certified_runtime_launcher `
  --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
  --automated-paper --max-cycles 1
```

Five cycles:

```powershell
venv\Scripts\python.exe -m services.paper_orchestration.certified_runtime_launcher `
  --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
  --automated-paper --max-cycles 5
```

Thirty cycles:

```powershell
venv\Scripts\python.exe -m services.paper_orchestration.certified_runtime_launcher `
  --factory services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
  --automated-paper --max-cycles 30
```

For a read-only launch, replace `--automated-paper` with `--observe-only`.
`--emergency-halt` keeps monitoring allowed while suppressing new entries.

## During the run

- Stop gracefully with Ctrl+C. The launcher records a stop/interruption event.
- Do not edit journals, P7, P8, or the runtime JSONL while the runtime is
  running.
- Do not treat a no-trade cycle as an error. It is expected when evidence is
  not eligible or no setup is present.
- If SmartAPI reports a rate limit, allow the request controller cooldown and
  bounded retry policy to operate; do not start competing runtime processes.

## Post-run inspection

Create both reports:

```powershell
venv\Scripts\python.exe scripts\summarize_paper_runtime.py `
  --input data\paper_trading\certified_runtime\runtime.jsonl `
  --output reports\paper_observation\runtime_summary.json `
  --text-output reports\paper_observation\runtime_summary.txt `
  --evidence data\paper_trading\certified_runtime\opportunity_orchestration_journal.json `
  --evidence data\paper_trading\certified_runtime\monitoring_orchestration_journal.json
```

Inspect outer counters **and** the inner result strings/stage results. An outer
operation can be `COMPLETED` while its inner P7 lifecycle is `FAILED`.
For a no-position soak, `P7_MONITORING_FAILURE` with “no active certified P7
position” is an expected fail-closed observation, not a position-management
success.
