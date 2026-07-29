# P6D Three-target trade-plan contract

## Purpose
Immutable PAPER-only validated three-target plan; it calculates nothing.
## Architectural boundary
No contract selection, entry/stop/target/sizing/cost/expiry calculation, order, execution, or portfolio sharing.
## Expiry representation
READY requires a supplied date-only expiry, supplied non-negative days to expiry, and WEEKLY or MONTHLY category. The selected contract expiry must match; same-day is zero. No weekday assumption or derivation occurs.
## Three-target representation
READY uses three `TradePlanTargetV1` children. Premiums are INR per unit, fractions use 0–1, and quantity is lot size times lot count.
## Serialization and immutability
Semantic serialization excludes only plan ID, evaluation time, and source timestamps.
## PAPER-only guarantees
Live execution remains disabled.
## P6E handoff
Future evaluators supply validated values.
