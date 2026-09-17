# P6H-3 Option-contract selector core

## Purpose

Deterministically selects the first direct-eligible candidate from P5 ranking.

## Architectural boundary

No raw option-chain ranking, quote fetching, date calculation, hardcoded lot
sizes, charges, slippage, final sizing, order creation, or execution occurs.

## Public API

`select_option_contract(input, policy)` accepts exact typed inputs.

## Ranked candidate source

Only `option_ranking_result.ranked_candidates` is used, unchanged in order and score.

## Evaluation order

Early blocks precede resolved-policy coherence and ranking availability. Candidate
checks are identity, right, premium validity/limit, spread availability/limit,
moneyness category, attached evidence, evidence moneyness/expiry/DTE, OI,
volume, liquidity, lot size, then affordability.

## Early planning blocks

Input, planning, session, event, policy, and ranking availability blocks are stable.

## Policy coherence

Policy ID and stricter premium/spread caps are used.

## Identity and option right

Candidates must match supplied canonical identity and option right.

## Premium validation

Uses typed last price with no cap mutation.

## Spread validation

Uses canonical candidate spread percent; no quote fetch occurs.

## Direct candidate checks

Direct moneyness, OI, volume, liquidity, and positive lot evidence are checked.

## Basic affordability

Premium times typed lot size and floor capital division only; no final quantity sizing.

## First-valid selection

The first passing ranked candidate is READY.

## Ranked fallback

Later selection appends one stable fallback warning.

## NO_CONTRACT outcome

Candidate exhaustion remains NO_CONTRACT with stable rejection classes.

## Diagnostics

Diagnostics preserve first occurrence.

## Determinism and provenance

Caller timestamps and ranking/policy IDs are preserved in deterministic metadata.

## Serialization boundary

The result contract owns serialization.

## PAPER-only guarantees

Live execution is disabled.

## P6H-4 matrix behavior

Resolved constraints govern all caps, minimums, moneyness and expiry permissions.
Candidate diagnostics and immutable provenance preserve candidate rank, attached
evidence fields, affordability inputs, and first-occurrence rejection order.

## P6H-4 handoff

P6H-4 extends only typed direct evidence.
