# P6H Final certification

## Scope
P6H certifies typed, deterministic PAPER-only option-contract selection.

## Certified contracts
Input, result, and supplemental evidence are immutable typed contracts.

## Certified resolver
Effective constraints are deterministic and impossible policies block early.

## Certified selector
First-valid selection consumes only ranked candidates.

## Ranked candidate source
No raw ranking, rescoring, sorting, or local optimization occurs.

## Effective constraints
Resolved stricter caps, minimums, intersections, and bounds govern checks.

## Supplemental eligibility evidence
Evidence is caller supplied and looked up only by canonical candidate ID.

## Candidate validation order
Identity, right, premium, spread, moneyness, evidence, expiry/DTE, OI, volume, liquidity, lot, affordability.

## READY behavior
READY preserves selected rank/score, complete eligibility and affordability evidence.

## BLOCKED behavior
Early blocks retain stable order; policy details remain metadata-only.

## NO_CONTRACT behavior
Candidate exhaustion remains NO_CONTRACT with stable rejection provenance.

## Premium and spread
Typed ranking fields and effective limits only; no quote fetch.

## Moneyness
Category intersection and supplied steps only; no spot derivation.

## Expiry and DTE
Supplied evidence only; no date arithmetic.

## Liquidity, OI, and volume
Resolved effective thresholds use ranking-native values.

## Lot size and affordability
Typed lot size, premium multiplication and floor only; no charges or final sizing.

## Deterministic replay
Fixed fixtures replay identically across all four supported markets.

## Serialization and immutability
Public serialization is stable and detached.

## Diagnostic ordering
First occurrence ordering is preserved.

## Metadata and provenance
Effective constraints and candidate evidence/affordability provenance are immutable.

## Isolation boundary
No providers, brokers, execution, clocks, network, or numerical services.

## Regression boundaries
P5 and P6E/P6F/P6G boundaries remain compatible.

## Exact pytest results
Recorded by the certification run.

## PAPER-only guarantees
Live execution remains disabled.

## Deferred behavior
P6I, charges, sizing, orders and execution are not started.
