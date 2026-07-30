# P9 — Real-time PAPER Orchestration Implementation Plan

## Objective

Build one authoritative, deterministic, PAPER-only orchestration path for
repeated NIFTY and SENSEX analysis, opportunity construction, P6 planning,
P8 admission, P7 lifecycle execution, P8 reconciliation, persistence,
restart recovery, and continuous runtime execution.

## Locked authority chain

DATA
→ SESSION
→ ANALYSIS
→ OPPORTUNITY
→ P6 PLAN
→ P8 ADMISSION
→ P7 PAPER LIFECYCLE
→ P8 PORTFOLIO UPDATE
→ IMMUTABLE P9 CYCLE RESULT
→ PERSISTENCE JOURNAL

Existing-position monitoring uses:

P7 POSITION EVALUATION
→ P7 PERSISTENCE
→ P8 PORTFOLIO UPDATE
→ IMMUTABLE P9 CYCLE RESULT
→ PERSISTENCE JOURNAL

The journal and deterministic coordinator form the outer idempotency boundary.

## Work packages

### WP1 — Audit and contracts — COMPLETE

- Audited existing runtime and authority paths.
- Added orchestration policy, failure, stage, cycle-input, cycle-result,
  and journal-record contracts.
- Added deterministic serialization and import tests.
- Locked PAPER-only execution and caller-supplied identities.

### WP2 — Deterministic cycle foundation — COMPLETE

- Added atomic orchestration journal.
- Added duplicate and idempotency-conflict classification.
- Added deterministic cycle coordinator.
- Added P6 planning-stage integration.
- Added initial P7 and P8 state factories.
- Added certified new-entry PAPER lifecycle orchestration.

### WP3 — Complete cycle, monitoring, recovery, and runtime — COMPLETE

- Added complete opportunity-cycle execution.
- Added existing-position monitoring execution.
- Enforced P7 mutation before P8 projection.
- Added immutable stage and cycle result construction.
- Added startup restart recovery.
- Added continuous runtime adapter.
- Preserved per-operation isolation and graceful stop behavior.
- Preserved PAPER-only import isolation.

### WP4 — Final certification and closure — COMPLETE

- Added authority-chain and public-export matrices.
- Added repository AST safety checks.
- Added sequential repeated-cycle certification.
- Added restart, replay, duplicate, and conflict certification.
- Added multi-position and portfolio consistency certification.
- Added corruption and startup-failure certification.
- Reconciled P9 documentation with the implemented architecture.
- Certified the full repository suite.

## Authoritative stage names

- `DATA`
- `SESSION`
- `ANALYSIS`
- `OPPORTUNITY`
- `P6_PLAN`
- `P8_ADMISSION`
- `P7_LIFECYCLE`
- `P8_PORTFOLIO_UPDATE`
- `PERSISTENCE`

## Authoritative cycle statuses

- `COMPLETED`
- `COMPLETED_NO_ACTION`
- `BLOCKED`
- `FAILED`
- `DUPLICATE_NO_CHANGE`

## Runtime boundary

`ContinuousPaperTradingRuntime` remains the outer scheduling primitive only.

It owns:

- startup execution
- repeated-cycle timing
- non-overlap
- graceful stop handling
- per-operation isolation

It does not own:

- market-data authority
- session authority
- analysis authority
- P6 planning
- P7 lifecycle decisions
- P8 portfolio decisions
- journal idempotency classification
- broker or live-order execution

## Closure criteria

P9 is closed only when all of the following are true:

1. All P9 tests pass.
2. The full repository test suite passes.
3. `git diff --check` passes.
4. relevant packages compile successfully.
5. PAPER-only import isolation remains green.
6. no live order executor, order manager, broker placement, or legacy
   paper-engine authority is introduced.
7. the working tree is clean after the final commit.
