# P7F Partial exits and P&L
## Purpose
Deterministic PAPER exit accounting.
## Position snapshot authority
PaperTradePositionV1 remains the snapshot authority.
## Fill authority
PaperTradeFillV1 records every SELL exit.
## P&L evidence
Immutable P&L evidence records each calculation.
## Realized gross P&L
Exit minus entry premium times exited quantity.
## Entry-cost allocation
Initial cost is allocated proportionally to exited quantity.
## Exit-cost evidence
Only caller supplied exit costs are used.
Cancellation uses its separate caller-supplied cancellation exit-cost field.
Invalidation uses the explicit invalidation exit-cost field and allocates the
remaining proportional entry cost at full closure.
## Realized net P&L
Gross less allocated entry and exit costs.
## Unrealized P&L
Current option premium less entry premium times remaining quantity.
## Total P&L
Realized net plus unrealized.
## Partial-exit accounting
Remaining quantity is exact lots times lot size.
## Full-close accounting
Terminal positions have zero unrealized P&L.
## Target attribution
Target fills retain T1/T2/T3 attribution.
## Runner accounting
Runner stays P6 allocated.
## Numeric invariants
Finite, coherent cumulative values.
## Serialization and immutability
Frozen, deterministic JSON.
## PAPER-only guarantees
No live execution.
## Prohibited behavior
No market fetch, broker order, persistence, existing-engine adapter, portfolio capital management, or live execution.
## P7-WP4 handoff
No WP4 behavior is included.
