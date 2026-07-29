# P6H-4C4 Comprehensive selector matrix

## Purpose

Certify deterministic first-valid selection over already-ranked typed candidates.

## Architectural boundary

No raw ranking, rescoring, evidence derivation, date calculation, hardcoded lot size, charges, final quantity sizing, order, or execution occurs.

## Early selector order

Exact types, input blockers, planning, session, event, policy coherence, ranking availability, then candidates.

## Candidate validation order

Identity, right, premium, spread, moneyness, evidence, expiry/DTE, OI, volume, liquidity, lot size, affordability.

## Ranked candidate reuse

Only ranking order and canonical score are reused; there is no sorting or local optimization.

## Identity and right

Canonical market identity and required option right are enforced.

## Premium

Typed premium and resolved cap are used without mutation.

## Spread

Ranking-native spread and resolved limit are used without quote fetching.

## Moneyness

Resolved category intersection and supplied evidence steps are used.

## Supplemental evidence

Evidence is retrieved only by candidate ID; it is never inferred.

## Expiry and DTE

Supplied category and DTE are checked without calendar arithmetic.

## Open interest

Resolved effective minimum is enforced.

## Volume

Resolved effective minimum is enforced.

## Liquidity

Resolved ranking-native threshold is enforced without scale conversion.

## Lot size and affordability

Typed lot size, premium multiplication, floor affordability and resolved bounds only; no charges or final sizing.

## READY outcome

The first passing ranked candidate preserves its score, rank, provenance and PAPER-only fields.

## BLOCKED outcome

Early blocks retain stable order and detailed policy codes stay metadata-only.

## NO_CONTRACT outcome

Ordinary exhaustion has deterministic, de-duplicated candidate diagnostics and no selected group.

## Diagnostic ordering

Candidate and rule first occurrence order is preserved.

## Metadata schema

Metadata includes ranking/policy IDs, effective constraints, stage, selected affordability fields, and immutable per-candidate evidence and affordability diagnostics.

## Determinism and isolation

JSON is stable; no runtime state, providers, network, clock, parsing or numerical libraries are used.

## PAPER-only guarantees

Live execution is disabled.

## Deferred replay certification

This is not final replay certification.

## P6H-5 handoff

P6H-5 may certify replay only; P6I remains unstarted.
