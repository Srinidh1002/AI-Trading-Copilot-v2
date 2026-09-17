# Certified PAPER Session Runbook

## Completed implementation

- Batches 1–7: safety, typed boundaries, live-read authorities, P5/P6
  boundaries, P7/P8 factories, monitoring, persistence, dashboard publication,
  controls, logging, and launcher
- Batch 8: repository-owned observe-only runtime composition

## Batch 8 factory

```text
services.paper_orchestration.certified_runtime_composition:
build_certified_launcher
```

It composes repository PAPER safety validation, live market readers, exact
DATA/SESSION/ANALYSIS/OPPORTUNITY authorities, exact cycle identities,
separate journals, P7/P8 persistence repositories, dashboard publication,
operator controls, continuous scheduling, JSON-line logs, and graceful
shutdown.

## Capability boundary

Batch 8 is deliberately observe-only. P6 planning and new PAPER entries fail
closed. This certifies live reads, analysis, opportunities, journals,
dashboard publication, controls, and shutdown without creating simulated or
broker positions.

## One-cycle command

```powershell
venv\Scripts\python.exe -m `
services.paper_orchestration.certified_runtime_launcher `
--factory `
services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
--observe-only `
--max-cycles 1
```

## Three-cycle command

```powershell
venv\Scripts\python.exe -m `
services.paper_orchestration.certified_runtime_launcher `
--factory `
services.paper_orchestration.certified_runtime_composition:build_certified_launcher `
--observe-only `
--max-cycles 3
```
