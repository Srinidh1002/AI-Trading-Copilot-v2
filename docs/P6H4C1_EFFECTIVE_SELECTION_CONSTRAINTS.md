# P6H-4C1 Effective selection constraints

## Purpose

Deterministically resolve compatible input and policy constraints.

## Architectural boundary

No P5 changes, candidate evaluation, evidence derivation, date calculation, lot lookup, order, or execution.

## Public resolver API

`resolve_option_contract_selection_constraints(input, policy)` returns a frozen typed result.

## Typed resolver result

Contains resolved caps, minimums, permissions, bounds, coherence, and stable codes.

## Maximum constraints

Present maxima use the lower value.

## Minimum constraints

Minimums use the higher value.

## Allowed-moneyness intersection

Canonical ATM/ITM/OTM intersection is used.

## Expiry permission intersection

Weekly, monthly, and same-day permissions require both values true.

## Policy-field availability

All named policy fields are present in current `TradePlanningPolicyV1`.

## Impossible effective policy

Empty moneyness/expiry permissions and incoherent lot/DTE/same-day bounds are typed incoherences.

## Diagnostic ordering

Policy mismatch, moneyness, lot, DTE, expiry, same-day.

## Selector integration

Reserved for minimal later wiring; this task does not enforce supplemental evidence.

## Determinism and serialization

Frozen deterministic JSON serialization is provided.

## PAPER-only guarantees

No runtime services or execution.

## Deferred candidate enforcement

Candidate enforcement is deferred to P6H-4C2.

## P6H-4C2 handoff

P6H-4C2 may consume the typed result.
