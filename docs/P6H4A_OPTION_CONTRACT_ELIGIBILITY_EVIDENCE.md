# P6H-4A Option-contract eligibility evidence

## Purpose

Caller-supplied immutable evidence for missing candidate eligibility fields.

## Why supplemental evidence is required

P5 ranking does not carry canonical moneyness steps, expiry category, or DTE.

## Architectural boundary

P5 ranking remains unchanged; this contract does not rank or select candidates.

## Candidate identity

It preserves the existing candidate identifier and typed option identity.

## Moneyness-step evidence

Nonnegative caller-supplied absolute steps; no spot-based derivation occurs.

## Expiry-category evidence

Caller supplies WEEKLY or MONTHLY; no expiry-date inference occurs.

## Days-to-expiry evidence

Caller supplies nonnegative DTE; expiry date is not used to calculate it.

## Evidence timestamp and source

Both are supplied, stable typed evidence.

## Provenance and metadata

JSON-safe immutable provenance supports approved upstream boundaries.

## Serialization and immutability

Detached deterministic JSON and semantic serialization are provided.

## PAPER-only guarantees

No quote fetch, order, execution, or live eligibility.

## Prohibited derivations

No spot, current-date, trading-symbol, or provider-payload derivation.

## Deferred attachment and selector behavior

P6H-4A does not attach evidence or alter selection.

## P6H-4B handoff

P6H-4B may attach this evidence to a typed selection request.
