# P7E Deterministic open-position evaluator
## Purpose
Pure PAPER post-entry evaluation.
## Input authority
Immutable position, policy, lifecycle state, and caller observation.
## Option-premium trigger authority
Only option premium evidence triggers exits.
## Evaluation order
Ordering, freshness, quality, expiry, session, typed cancellation, typed invalidation, stop, then targets. Cancellation is machine-readable only, uses one `CANCELLED` fill, and cannot share an evaluation with invalidation, stop, or targets.
## Invalidation authority
The input exposes `ABSENT`, `NOT_TRIGGERED`, or `TRIGGERED`; only TRIGGERED
with a nonblank machine-readable reason closes the remaining position. No
natural-language diagnostics are parsed. Invalidation uses option last price,
is after expiry/session and before stop/targets.
## Stop processing
Stops close remaining lots.
## Target processing
Targets consume only copied P6 allocations.
## Same-observation precedence
Policy controls STOP_FIRST, CONSERVATIVE_STOP_FIRST, or TARGET_FIRST.
## Multiple-target crossing
Policy controls sequential or highest-crossed processing.
## Partial exits
New immutable snapshots retain remaining lots.
## Runner handling
Runner allocation remains P6 authority.
## Session close
Caller session evidence may close remaining lots.
## Expiry close
Caller timestamp and P6 expiry date control expiry close.
## Observation ordering
Duplicates no-op and out-of-order observations block when policy requires.
## HOLD behavior
HOLD updates only derived unrealized P&L.
## Lifecycle output
Result exposes the resulting lifecycle vocabulary.
## Determinism
No clock, network, or mutation.
## PAPER-only guarantees
Exact PAPER mode; live disabled.
## Prohibited behavior
No market fetch, broker order, persistence, existing-engine adapter, portfolio capital management, or live execution.
## P7-WP4 handoff
No WP4 behavior is included.
