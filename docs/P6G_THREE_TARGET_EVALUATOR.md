# P6G Three-target evaluator

## Purpose

Creates exactly three deterministic option-premium INR-per-unit target intents.

## Architectural boundary

Consumes only policy and supplied typed evidence; no market data, lot allocation,
sizing, option selection, order, or execution is performed.

## Input contract

Immutable caller-supplied entry/stop/target evidence, diagnostics, provenance,
and PAPER fields. Fractions use 0–1.

## Result contract

READY supplies exactly three ordered `TradePlanTargetV1` values; BLOCKED and
NO_TARGETS support absent groups.

## Target methods

RISK_MULTIPLE, ATR, EXPECTED_MOVE, STRUCTURE, and HYBRID are supported.

## Risk-multiple method

Adds stop distance times each policy multiplier to option entry.

## ATR method

Adds supplied ATR times each target multiplier; P6G fetches no ATR.

## Expected-move method

Adds supplied expected move times policy multipliers.

## Structure method

Uses complete explicit premium targets, otherwise the first three increasing
resistance levels above entry.

## Hybrid method

Chooses the valid candidate set with highest T2 RR, using structure, expected
move, ATR, and risk-multiple tie priority.

## Allocation intent

Policy allocations are copied exactly; no target lot allocation is calculated.

## Reward-to-risk

Reward is target minus entry; RR is reward divided by stop distance.

## Planning eligibility

Planning, policy, and entry/stop coherence block before target calculation.

## Diagnostics

Diagnostics remain deterministic and deduplicated.

## Determinism and provenance

Caller IDs/timestamps and source timestamps are preserved; JSON is stable.

## Serialization and immutability

Frozen typed contracts expose detached deterministic serialization.

## PAPER-only guarantees

No market data, sizing, selection, order, or execution; live execution disabled.

## Deferred behavior

No P6H work was started.

## P6H handoff

Future P6H may consume this typed target result only.
