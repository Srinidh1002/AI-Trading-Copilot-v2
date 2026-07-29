# P7C Paper position contracts
## Purpose
Immutable PAPER market observation, fill, and initial OPEN position evidence.
## Architectural boundary
No engine, persistence, order, broker, provider, valuation, or P&L behavior.
## Market observation contract
Caller-supplied option and contextual underlying evidence with coherent optional OHLC.
## Price-basis authority
P6E `entry_reference_price`/zone are selected-option-premium values; only option evidence activates entry.
## Paper fill contract
PAPER fill evidence validates quantity, notional, and cash coherence; it is not an order.
## Paper position authority
P7 typed initial OPEN snapshot; WP3 extends exit states.
## Entry sizing authority
P6I planned lots and quantity are copied unchanged.
## Target-allocation authority
P6I T1/T2/T3/runner allocations are copied unchanged.
## Risk and cost authority
P6I risk/cost values are copied; no recalculation.
## Lifecycle-state relationship
WP2 creates only OPEN positions from an ENTRY/BUY fill.
## P&L initialization
All P&L fields are zero; no calculation is performed.
## Serialization and immutability
Frozen contracts with deterministic JSON and detached metadata.
## PAPER-only guarantees
Exact PAPER mode and false live eligibility.
## Prohibited behavior
No orders, execution, persistence, or provider calls.
## Deferred P7-WP3 behavior
Only exit fills, partial exits, and realized/unrealized P&L updates are deferred; WP2 OPEN snapshots, P6 value copying, and zero-P&L initialization are implemented.
