# P6C Trade-planning policy
## Purpose
Pure immutable PAPER-only rules; values do not calculate a plan.
## Architectural boundary
No broker, provider, order, portfolio, or execution dependency.
## Risk controls
INR risk limits and 0–1 fractions are explicit.
## Stop-loss policy
Controlled ATR/structure/premium/hybrid methods only.
## Entry-zone policy
Reference method and tolerance fractions only.
## Three-target policy
Ordered RR/multipliers and allocation intent are explicit.
## Target allocations
Fractions sum to one; quantity is not calculated.
## Option-contract restrictions
Premium, spread, liquidity, moneyness, and steps are rules only.
## Lot and quantity restrictions
Lot bounds and insufficient-target behavior are explicit.
## Cost and slippage assumptions
INR brokerage and 0–1 assumptions only.
## Expiry restrictions
No expiry is selected.
## Event restrictions
Buffers/categories are policy data only.
## Session restrictions
No session calculation occurs.
## Confidence thresholds
P5-compatible 0–1 thresholds.
## Cross-field validation
Ordering, sums, expiry and PAPER coherence fail loudly.
## Serialization and immutability
Frozen deterministic JSON serialization.
## PAPER-only guarantees
No strike, quantity, plan, order, or live execution is created.
## P6D handoff
P6D owns output contract.
