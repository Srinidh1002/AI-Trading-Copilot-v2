# B3 Snapshot Persistence and Replay V1

## Purpose

B3 Step 2 provides deterministic persistence and exact offline reconstruction
of `MarketSnapshotV1`.

A persisted record must be usable without FYERS, broker connectivity, live
market access, or the trading runtime.

## Record envelope

Each record contains exactly:

- record schema version;
- snapshot schema version;
- declared snapshot SHA-256;
- canonical snapshot payload.

The persisted form uses deterministic compact JSON plus one trailing newline.

## Integrity verification

Replay performs multiple checks.

### 1. Strict JSON decoding

Replay rejects:

- invalid JSON;
- duplicate object keys;
- non-finite JSON constants;
- unexpected envelope fields.

### 2. Schema verification

Replay validates:

- record schema;
- snapshot schema;
- registry schema;
- evidence schema;
- analyzer-result schema.

### 3. Stored payload hash

The canonical stored snapshot payload is independently serialized and hashed.

That digest must match the stored `snapshot_sha256`.

### 4. Object reconstruction

Every persisted evidence object is reconstructed as `EvidenceV1`.

Every analyzer result is reconstructed as `AnalyzerResultV1`.

The full record is reconstructed as `MarketSnapshotV1`.

Normal constructor validation therefore runs again during replay.

### 5. Reconstructed snapshot identity

The reconstructed snapshot recomputes its own canonical SHA-256.

It must equal the stored digest.

### 6. Canonical JSON equivalence

The reconstructed `MarketSnapshotV1.canonical_json()` must exactly equal the
canonical JSON representation of the stored payload.

## Failure behavior

The replay path fails closed for:

- truncated JSON;
- malformed UTF-8;
- duplicate JSON keys;
- unsupported schemas;
- missing or extra fields;
- invalid SHA-256 formatting;
- payload/hash mismatch;
- authority promotion;
- invalid evidence;
- invalid analyzer results;
- invalid MarketSnapshot content.

## Persistence behavior

A target path containing identical record bytes is idempotent.

A target path containing different bytes causes
`SnapshotPersistenceConflictError`.

The implementation first writes and fsyncs a temporary file in the target
directory, then publishes it using an atomic no-overwrite hard-link operation.

If another writer wins the target name first:

- identical bytes are treated as idempotent success;
- different bytes fail with `SnapshotPersistenceConflictError`;
- the competing record is never overwritten.

This closes the check-then-replace race that would otherwise exist between a
final target existence check and publication.

## Security scope

SHA-256 provides deterministic content integrity and change detection.

This format is **not digitally signed**.

An attacker who can modify both a record and its digest can manufacture a new
self-consistent record. Cryptographic authenticity/signing is a separate
future hardening concern.

## Authority boundary

Persistence and replay do not gain:

- execution authority;
- decision authority;
- risk authority;
- position-management authority;
- certification authority;
- provider access;
- broker access.

Replayed snapshots remain observation-only.

## Production isolation

This module is not imported by the running NIFTY, SENSEX, MCX or supervisor
entrypoints.

The R2.2 PAPER certification campaign remains independent.

## Next step

After persistence/replay is frozen, B3 can proceed to a snapshot journal /
capture coordinator.

That layer will organize multiple immutable snapshots by market/session while
still remaining shadow-only.

Only after reproducible capture and replay are proven should B4 introduce a
Shadow Brain consuming these snapshots.