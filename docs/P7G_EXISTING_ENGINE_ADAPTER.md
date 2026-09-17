# P7G Existing PaperTradingEngine adapter

## Purpose

`PaperTradingEngineAdapterV1` is an explicit, opt-in bridge for typed P7 requests.

## Existing engine authority

The existing engine retains its public legacy `open_trade` behavior and legacy references.

## Typed P7 authority

Typed lifecycle, position, fills, observations, and P&L remain authoritative.

## Opt-in integration

No legacy caller is routed through the adapter; callers construct it explicitly.

## P6J translation

Entry activation translates copied position/P6J values only; quantity, lot size, stop, T1 and capital evidence are not recalculated.

## Legacy-result translation

Only the legacy trade ID is retained; incomplete legacy values never replace typed evidence.

## Identity mapping

Caller paper-trade and idempotency IDs are durable typed identities.

## Idempotency

The durable snapshot stores a semantic payload hash for each caller key.

## Duplicate prevention

Same key/same payload returns the prior typed snapshot; a conflict is BLOCKED.

## BLOCKED behavior

Conflicting payloads do not mutate persistence.

## Compatibility guarantees

`PaperTradingEngine` is not modified or replaced.

## PAPER-only guarantees

All adapter contracts reject non-PAPER execution.

## Prohibited behavior

No provider fetch, broker order, live execution, or P6 calculation occurs.

## Manual cancellation traceability

`CANCEL_PAPER_TRADE` is available only through typed `REQUESTED` cancellation authority. It persists typed P7 state and does not invoke legacy or live cancellation behavior.

## Return-percentage traceability

Deferred: P7 has no authoritative denominator convention; P&L remains monetary.

## P7H handoff

Typed snapshots use the existing atomic `PaperTradeRepository`.
