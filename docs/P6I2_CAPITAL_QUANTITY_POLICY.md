# P6I-2 Capital and quantity planning policy

## Purpose
Immutable supplemental PAPER-only policy for future capital planning.
## Architectural boundary
Canonical available capital remains upstream; this policy contains no trade-specific capital.
## Capital utilization
Required 0–1 maximum fraction.
## Reserve capital
Nonnegative policy reserve; feasibility is deferred.
## Risk models
PREMIUM_AT_RISK and caller-supplied per-lot-risk vocabulary only.
## Risk limits
At least one positive fraction or amount is required; no risk budget is calculated.
## Planned lot bounds
Exact positive inclusive bounds.
## Target-allocation policy
Optional three weights; no target lots are calculated.
## Target remainder priority
Fixed T1, T2, T3 property.
## Provenance
Caller timestamp, source, warnings, timestamps and frozen metadata.
## Serialization and immutability
Stable detached JSON; semantic serialization excludes ID and provenance timestamps.
## PAPER-only guarantees
Live execution disabled.
## Prohibited behavior
No sizing, quantity, charges, taxes, slippage, orders, or execution.
## Deferred P6I-3 input contract
Trade-specific coherence and supplied risk evidence are deferred.
## P6I-3 handoff
P6I-3 may consume this policy only.
