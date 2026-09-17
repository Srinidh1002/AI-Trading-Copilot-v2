# P7H Persistence and recovery

## Purpose

Persist and validate canonical typed P7 snapshots.

## Existing storage authority

The existing JSON `PaperTradeRepository` remains storage authority.

## Persisted snapshot

The envelope stores version, IDs, lifecycle policy/state, position, observation, P&L, event sequence, timestamps, and integrity hash.

## State and position persistence

Immutable typed serialization is stored as JSON only.

## Fill persistence

Entry and ordered exit fills are nested in the position snapshot.

## P&L persistence

Latest cumulative typed P&L evidence is stored when produced.

## Observation evidence

The latest typed observation is preserved.

## Idempotency persistence

Key and semantic payload hash are stored atomically with the snapshot.

## Transaction boundary

Existing repository atomic file replacement is the strongest available boundary.

## Recovery validation

Decoder reconstructs exact typed contracts; contract invariants reject incoherence.

## Corruption handling

Malformed/missing/integrity-mismatched snapshots fail closed.

## Active-position recovery

Only nonterminal snapshots are returned by `recover_active`.

## Terminal-history loading

Terminal snapshots load as history and are not replayed.

## Restart behavior

Durable keys prevent repeated processing after restart.

## Deterministic event order

Snapshots sort by `(created_at, paper_trade_id)` and carry event sequence.

## PAPER-only guarantees

Snapshot validation enforces PAPER and false live eligibility.

## Prohibited behavior

No new database, pickle, broker, or provider integration.

## P7I handoff

Replay uses recovered immutable snapshots.
