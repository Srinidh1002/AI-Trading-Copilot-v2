# P7 Paper-trade lifecycle implementation plan

## Objective
Provide deterministic PAPER-only lifecycle processing after final P6 planning.
## Final P6 input authority
`IntegratedThreeTargetTradePlanResultV1`; P7 never recalculates its planning fields.
## Existing PaperTradingEngine compatibility authority
`services/paper_trading_engine.py::PaperTradingEngine` remains unchanged.
## New typed lifecycle authority
P7B policy/state contracts and pure transition table.
## Lifecycle state model
PLANNED, WAITING_FOR_ENTRY, OPEN, PARTIALLY_EXITED, target/stop/invalidation/session/expiry closures, CANCELLED, BLOCKED.
## Legal transition model
Only the documented transition matrix; terminal states never reopen.
## Entry activation boundary
WP2 evaluates caller-supplied observations.
## Open-position evaluation boundary
WP3 evaluates already-open positions.
## Partial-exit boundary
WP3 only.
## P&L boundary
WP3 only; legacy P&L remains isolated.
## Persistence and recovery boundary
WP4 adapter and replay; no schema change in WP1.
## Idempotency boundary
WP2 observation ordering; WP4 engine/repository adaptation.
## Adapter boundary
WP4 maps typed states to existing engine/repository compatibility APIs.
## Public API plan
Lazy contracts export now; evaluator/adapter exports later.
## Work-package sequence
- P7-WP1: audit, lifecycle policy, lifecycle state
- P7-WP2: position/fill/observation contracts and entry evaluator
- P7-WP3: open-position evaluator, partial exits, and P&L
- P7-WP4: existing-engine adapter, persistence/recovery, replay, and final P7 certification
## P7-WP2 scope
No P&L or persistence.
## P7-WP3 scope
No existing-engine replacement.
## P7-WP4 scope
Compatibility adapter and deterministic recovery certification.
## Certification strategy
Focused contract, isolation, transition, P6J, then existing paper-engine regressions.
## PAPER-only guarantees
Exact `PAPER`, false live eligibility, no broker/order calls.
## Prohibited behavior
No live execution, provider fetch, engine modification, or P6 recalculation.
