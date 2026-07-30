# Certified PAPER Session Runbook

## Current implementation status

Completed:

- Batch 1: fail-closed runtime safety boundary
- Batch 2: deterministic typed cycle identities and exact cycle input
- Batch 3: read-only DATA, SESSION, ANALYSIS, and OPPORTUNITY authorities
- Batch 4: concrete NIFTY/SENSEX readers and exact P6 boundary
- Batch 5: typed P5 selection and exact P7/P8 new-entry composition
- Batch 6: monitoring, journals, and restart recovery
- Batch 7: dashboard publication composition, operator controls, JSON logging,
  executable launcher, and graceful shutdown handling

## Dashboard publication

Batch 7 constructs one exact `DashboardPublicationStore` and one exact
`DashboardRuntimePublicationProducer` sharing that store.

The continuous runtime adapter registers the store and publishes both
opportunity and monitoring cycle results. Failed publications retain the
last-known-good dashboard snapshot.

## Operator modes

### Observe-only

- analysis continues
- opportunity cycles continue
- new PAPER entries are fail-closed
- existing-position monitoring continues

### Entry-enabled PAPER

- new PAPER entries may proceed through certified P6/P8/P7 only
- broker order submission remains unavailable

### Emergency PAPER halt

- new PAPER entries are fail-closed
- existing-position monitoring continues
- operator state remains visible in structured logs

## Structured logs

Default recommended location:

```text
data/paper_trading/certified_runtime/runtime.jsonl
```

Every log record includes:

- timezone-aware event time
- `execution_mode=PAPER`
- `live_execution_eligible=false`
- event-specific fields
- recursive secret redaction for PIN, password, secret, token, API key, and
  TOTP-shaped field names

## Executable launcher

The launcher accepts a repository-owned composition factory:

```powershell
venv\Scripts\python.exe -m `
services.paper_orchestration.certified_runtime_launcher `
--factory your_module:build_certified_launcher `
--observe-only `
--max-cycles 1
```

The factory must return exact `CertifiedLauncherCompositionV1`. This keeps
provider credentials and repository-specific construction outside the generic
launcher while still requiring the certified runtime adapter.

## Graceful shutdown

SIGINT, SIGTERM, and KeyboardInterrupt request runtime stop. Signal handlers
are restored after execution. Completion, interruption, and failure are
written to the JSON-line log.

## Remaining certification before a live market session

- repository-owned final composition factory
- one-cycle observe-only smoke run
- journal/database backup
- final safety-limit review
- full test suite
- API-key revocation confirmation for any previously exposed key
