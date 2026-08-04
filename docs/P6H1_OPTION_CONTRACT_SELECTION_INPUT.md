# P6H-1 Option-contract selection input

## Purpose

Immutable PAPER-only attachment of ranked candidates and planning constraints.

## Architectural boundary

Ranked candidates come only from `OptionContractRankingResultV1`; no raw chain
ranking, quote fetch, candidate evaluation, selection, lot sizing, order, or execution.

## Ranking-result attachment

Exact typed ranking result identity, market, direction, and right must match.

## Identity and direction

Canonical markets and BULLISH/CALL or BEARISH/PUT are enforced.

## Capital and premium constraints

Positive INR capital and optional positive premium cap are represented only.

## Spread and liquidity constraints

Optional 0–1 spread and ranking-native liquidity constraints are immutable.

## Moneyness constraints

ATM, ITM, and OTM tuple constraints are normalized and unique.

## Lot constraints

Validated minimum/maximum lot-count intent; no sizing occurs.

## Expiry constraints

Weekly/monthly/same-day flags and coherent supplied DTE bounds are validated.

## Session and event context

Caller-supplied planning/session/event booleans are preserved.

## Diagnostics

Tuple diagnostics are trimmed, deduplicated, and immutable.

## Provenance and metadata

Aware source timestamps and deeply frozen JSON-safe metadata are detached.

## Serialization and immutability

Stable JSON and semantic serialization exclude only IDs/time/timestamps.

## PAPER-only guarantees

Live execution is disabled.

## Deferred selection behavior

P6H-1 does not select contracts.

## P6H-2 handoff

P6H-2 may evaluate only this typed input and its attached ranking evidence.
