# Certified PAPER Session Runbook

## Current implementation status

Completed:

- Batch 1: fail-closed runtime safety boundary
- Batch 2: deterministic typed cycle identities and exact cycle input
- Batch 3: read-only DATA, SESSION, ANALYSIS, and OPPORTUNITY authorities
- Batch 4: concrete NIFTY/SENSEX readers and exact P6 boundary
- Batch 5: typed P5 selection and exact P7/P8 new-entry composition
- Batch 6: existing-position monitoring, orchestration journals, and restart
  recovery composition

The executable launcher is still disabled.

## Existing-position monitoring

The certified monitoring factory requires:

- one exact persisted `PaperTradePersistenceSnapshotV1`
- an existing position inside that snapshot
- one exact `PaperPortfolioPolicyV1`
- one exact `PaperTradePositionEvaluationInputV1`
- matching P7 position identity
- evaluation timestamp equal to the monitoring cycle request timestamp

The cycle-owned P8 update event and idempotency identities are reused. The
resulting P8 snapshot ID is deterministic.

## Journal layout

Opportunity and monitoring cycles use separate atomic journals:

```text
data/paper_trading/certified_runtime/
  opportunity_orchestration_journal.json
  monitoring_orchestration_journal.json
```

Both journals remain under the certified PAPER data root. Sharing one journal
between opportunity and monitoring coordinators is rejected.

The existing deterministic coordinator provides:

- new-cycle classification
- duplicate-same-payload handling
- payload-conflict rejection
- exact result validation
- atomic journal persistence

## Restart recovery

Startup recovery accepts exact caller-supplied P7 trade IDs and P8 portfolio
IDs. Each target is recovered through its certified recovery authority.

The startup result succeeds only when every target reports `RECOVERED`.
Failure prevents continuous runtime cycles.

## Safety guarantees

- no broker order methods
- no credential access
- no live execution switches
- no arbitrary dictionary conversion into P7/P8 monitoring contracts
- separate opportunity and monitoring journals
- atomic journal writes
- fail-closed restart recovery
- `execution_mode=PAPER`
- `live_execution_eligible=False`

## Remaining implementation

- dashboard runtime publication composition
- executable launcher and structured logging
- observe-only and emergency-halt launcher controls
- graceful shutdown and session certification
