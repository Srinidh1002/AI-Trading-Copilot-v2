# P9 — Real-time PAPER Orchestration Implementation Plan

## WP1 — Audit and contracts
- Audit existing runtime paths.
- Add orchestration policy, failure, stage, cycle input, and cycle result contracts.
- Add deterministic serialization and import tests.

## WP2 — Single-cycle orchestration and idempotency
- Validate session and freshness.
- Consume typed analysis.
- Build or consume `TradeOpportunityV1`.
- Build or consume certified P6 plan.
- Evaluate P8 admission.
- Evaluate P7 entry or open-position lifecycle.
- Apply P7 result to P8.
- Persist state.
- Return one immutable cycle result.

## WP3 — Session controls and resilience
- Pre-open, regular, entry cutoff, management-only window, close, expiry-day, restricted event, and emergency halt controls.
- Missing candles, empty option chain, stale price, timeout, invalid typed result, persistence failure, and recovery behavior.

## WP4 — Continuous PAPER runner and replay
Wrap `ContinuousPaperTradingRuntime` with startup recovery, per-instrument isolation, deterministic cycle IDs, graceful shutdown, and PAPER-only import isolation.

## Initial stage names
DATA, SESSION, ANALYSIS, OPPORTUNITY, P6_PLAN, P8_ADMISSION, P7_LIFECYCLE, P8_PORTFOLIO_UPDATE, PERSISTENCE

## Initial cycle statuses
COMPLETED, COMPLETED_NO_ACTION, BLOCKED, FAILED, DUPLICATE_NO_CHANGE
