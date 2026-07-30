# P9A — Real-time PAPER Orchestration Audit

## Objective

Define one authoritative, deterministic, PAPER-only runtime path for repeated
NIFTY and SENSEX analysis, opportunity construction, P6 planning, P8
admission, P7 lifecycle updates, P8 reconciliation, persistence, restart
recovery, and continuous execution.

## Accepted authorities

- DATA: `LiveMultiTimeframeData`
- ANALYSIS: `LiveAnalysisPipeline`
- SESSION: `validate_session_timestamp()` plus typed session validation
- OPPORTUNITY: canonical trade-opportunity construction
- P6 PLAN: certified P6 planning integration
- P8: admission, reservation, aggregation, persistence, recovery, replay
- P7: PAPER lifecycle, fills, exits, P&L, persistence, recovery, replay
- JOURNAL: `PaperOrchestrationJournal`
- IDEMPOTENCY: `DeterministicPaperOrchestrationCycleCoordinator`
- LOOP: `ContinuousPaperTradingRuntime` through the P9 runtime adapter

## Rejected authorities

P9 must not import or call:

- `services.live.live_market_engine`
- `services.execution.order_executor`
- `services.execution.order_manager`
- broker order-placement functions
- legacy paper-executor fallbacks
- Streamlit as a transition owner
- `TradingScheduler` as orchestration authority
- `MarketClock` as session authority

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

## Outer boundaries

### Idempotency boundary

journal classification
→ deterministic cycle execution
→ result validation
→ atomic journal commit

### Runtime boundary

startup recovery
→ opportunity coordinator
→ monitoring coordinator
→ wait
→ repeat

The runtime controls scheduling and isolation only. It does not replace P6,
P7, P8, or journal authority.

## Safety invariants

1. PAPER-only execution mode.
2. `live_execution_eligible` is always false.
3. Caller-supplied or deterministically derived identities.
4. No hidden UUID generation in authoritative orchestration.
5. No broker order placement.
6. No false READY on missing or stale data.
7. No duplicate PAPER entry or exit.
8. No out-of-order state mutation.
9. P6, P7, and P8 remain sole authorities for their domains.
10. Streamlit is a reader, not a transition owner.
11. Persistence failure is fail-closed.
12. Corrupt persisted state is not treated as recovered.
13. Startup recovery failure prevents cycle execution.
14. One runtime lane failure does not suppress the other lane.
15. P7 state mutation precedes P8 projection.

## Closure result

P9 implementation and certification are complete.

Certified coverage includes:

- contract and export validation
- deterministic journal and coordinator behavior
- complete opportunity-cycle execution
- existing-position monitoring
- sequential repeated runtime execution
- restart and replay behavior
- duplicate and payload-conflict handling
- multi-position and multi-portfolio recovery
- persistence corruption behavior
- startup failure isolation
- AST-level PAPER-only repository safety

The final certification baseline is recorded in
`docs/P9_FINAL_CERTIFICATION_MATRIX.md`.
