# P6H-4B Option-contract evidence attachment

## Purpose

Attach immutable supplemental evidence to ranked candidates by canonical ID.

## Architectural boundary

P5 candidates remain unchanged and no selection decision occurs.

## Attached evidence collection

Only exact evidence contracts in a tuple are accepted.

## Candidate-ID matching

Orphan and duplicate evidence are rejected.

## Identity coherence

Market, right, symbol, strike, and expiry match the ranked candidate.

## Ranking-order normalization

Evidence serializes in ranked candidate order.

## Missing evidence behavior

Partial coverage is permitted.

## Lookup behavior

Immutable lookup returns evidence or None.

## Serialization and immutability

Evidence remains semantic and detached.

## PAPER-only guarantees

No provider fetch, selection decision, order, or execution.

## Prohibited derivations

No moneyness-step, expiry-category, or DTE calculation.

## Deferred selector enforcement

P6H-4C consumes attached evidence later.

## P6H-4C handoff

No P6H-4C work is included here.
