# P6H-2 Option-contract selection result

## Purpose

Immutable PAPER-only selected-contract result representation.

## Architectural boundary

This contract does not evaluate candidates, rank raw chains, fetch quotes, calculate affordability, size quantity, order, or execute.

## Selected-contract group

Contract, rank, and score are wholly present or absent.

## READY status

Requires group, all eligibility flags, affordability evidence, and no blockers.

## BLOCKED status

Requires blockers and no selected group.

## NO_CONTRACT status

Requires decision reasons and no selected group.

## Eligibility evidence

Each field is exact bool or None.

## Affordability evidence

Cost and lot count are validated, never calculated.

## Diagnostics

Tuple diagnostics are deterministic and immutable.

## Provenance and metadata

Timestamps and JSON-safe metadata are deeply detached.

## Convenience properties

Trading symbol, strike, expiry, lot size, and premium derive only from selected candidate fields.

## Serialization and immutability

Stable JSON and semantic serialization support deterministic replay.

## PAPER-only guarantees

Live execution is disabled.

## Deferred selector behavior

No selector logic exists in P6H-2.

## P6H-3 handoff

P6H-3 may create this result from typed selection evaluation only.
