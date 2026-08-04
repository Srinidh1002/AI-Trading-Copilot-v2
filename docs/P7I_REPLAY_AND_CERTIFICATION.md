# P7I Replay and certification

## Purpose

Coordinate deterministic typed position evaluation after recovery.

## In-process replay

The replay coordinator evaluates supplied immutable P7 input.

## Restart replay

Recovery reloads the same canonical snapshot before evaluation.

## Fresh-subprocess replay

Fresh writer and reader processes recover canonical OPEN, partial, and terminal snapshots without process-memory state. Duplicate observations remain economic no-ops and newer observations continue deterministically.

## Idempotent replay

Duplicate observations are typed no-ops and durable idempotency prevents duplicate adapter requests.

## Full lifecycle scenarios

Certified restart scenarios cover targets, runners, stop, session, expiry, typed invalidation, typed cancellation, duplicates, and terminal-history exclusion.

## NIFTY CALL

Preserved through typed position identity.

## NIFTY PUT

Preserved through typed position identity.

## SENSEX

Preserved through typed market and exchange identity.

## BLOCKED lifecycle

Corrupt or conflicting durable requests fail closed.

## Corruption rejection

Integrity and exact contract reconstruction reject bad snapshots.

## Existing-engine compatibility

The adapter is opt-in and does not replace the engine.

## Determinism

No generated timestamps, UUIDs, random values, network calls, or providers are used.

## Certification boundary

P7A through P7I are phase-certified by focused WP1-WP4 boundaries, existing paper-engine regressions, and the full repository suite.

## Remaining final P7 certification

Typed cancellation is implemented and certified. Return percentage remains explicitly deferred because premium outlay, estimated risk, and total capital requirement are distinct candidate denominators and no authoritative denominator exists; realized gross/net, unrealized, and total P&L remain authoritative.
