# P7B Lifecycle policy and state
## Purpose
Typed immutable lifecycle foundation.
## Architectural boundary
Pure contract validation only.
## Existing-engine compatibility
Existing `PaperTradingEngine` is unchanged; WP4 adapts it.
## Canonical lifecycle states
PLANNED, WAITING_FOR_ENTRY, OPEN, PARTIALLY_EXITED, CLOSED_TARGET_1, CLOSED_TARGET_2, CLOSED_TARGET_3, CLOSED_STOP, CLOSED_INVALIDATED, CLOSED_SESSION, CLOSED_EXPIRY, CANCELLED, BLOCKED.
## Terminal states
All CLOSED_*, CANCELLED, BLOCKED.
## Legal transitions
PLANNED→WAITING/CANCELLED/BLOCKED; waiting→OPEN/cancel/terminal blocked paths; OPEN→partial/terminal; partial→partial or eligible terminal paths.
## Illegal transitions
No terminal reopen, planned target close, waiting partial exit, or open waiting.
## Lifecycle policy
`PaperTradeLifecyclePolicyV1` is frozen and fail-closed.
## Entry controls
ZONE_TOUCH, PREFERRED_ENTRY_TOUCH, ZONE_CLOSE; tolerance, timeout, gap/freshness.
## Stop and target controls
TOUCH/CLOSE, explicit precedence and target-crossing mode.
## Same-observation precedence
STOP_FIRST, TARGET_FIRST, CONSERVATIVE_STOP_FIRST.
## Partial exits and runner controls
Runner requires partial exits; close mode is controlled.
## Session and expiry controls
Caller-configured close and holding-duration controls.
## Observation ordering
Duplicate/out-of-order controls are policy-only in WP1.
## Lifecycle state contract
IDs, states, supplied timestamps, terminal evidence, diagnostics.
## State invariants
Legal sequence, aware timestamps, terminal coherence, BLOCKED blockers.
## Transition helper
Pure `is_legal_paper_trade_lifecycle_transition`.
## Serialization and immutability
Frozen dataclasses, recursively frozen metadata, detached dicts, byte-stable JSON.
## Determinism
No clock, generated ID, network, or mutation.
## PAPER-only guarantees
`execution_mode='PAPER'`, live eligibility false.
## Prohibited behavior
No entry evaluation, position valuation, P&L, persistence write, existing-engine modification, market-data fetch, broker/provider integration, orders, or execution; live execution disabled.
## Deferred P7-WP2 behavior
Observation/fill/position contracts and entry evaluation.
## P7-WP2 handoff
Use P6J final plan plus P7B policy/state without recalculation.
