# P9A — Real-time PAPER Orchestration Audit

## Objective
Define one authoritative, deterministic, PAPER-only runtime path for repeated NIFTY and SENSEX analysis, opportunity construction, P6 planning, P8 admission, P7 lifecycle updates, and P8 reconciliation.

## Accepted authorities
- DATA: `LiveMultiTimeframeData`
- ANALYSIS: `LiveAnalysisPipeline`
- SESSION: `validate_session_timestamp()` + `MarketSessionValidationV1`
- OPPORTUNITY: `build_canonical_trade_opportunity()`
- P6 PLAN: `integrate_three_target_trade_plan()`
- P8: admission, reservation, aggregation, persistence, recovery, replay
- P7: PAPER lifecycle, fills, exits, P&L, persistence, recovery, replay
- LOOP: existing `ContinuousPaperTradingRuntime`

## Rejected authorities
P9 must not import or call:
- `services.live.live_market_engine`
- `services.execution.order_executor`
- `services.execution.order_manager`
- legacy paper-executor fallbacks
- Streamlit
- `TradingScheduler` as the runtime authority
- `MarketClock` as the session authority

## Locked authority chain
DATA → SESSION → ANALYSIS → OPPORTUNITY → P6 PLAN → P8 ADMISSION → P7 PAPER LIFECYCLE → P8 PORTFOLIO UPDATE → IMMUTABLE P9 CYCLE RESULT

## Safety invariants
1. PAPER-only execution mode.
2. Caller-supplied cycle and event identities.
3. No hidden UUID generation in authoritative orchestration.
4. No broker order placement.
5. No false READY on missing or stale data.
6. No duplicate PAPER entry or exit.
7. No out-of-order state mutation.
8. P6, P7, and P8 remain sole authorities for their domains.
9. Streamlit is a reader, not a transition owner.
10. Persistence failure is fail-closed.
