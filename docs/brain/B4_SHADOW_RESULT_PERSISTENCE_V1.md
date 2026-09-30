# B4 Shadow Result Persistence V1

## Purpose

`shadow_result_persistence_v1` provides deterministic immutable persistence and
strict replay for `ShadowBrainResultV1`.

It is a storage boundary only.

It does not evaluate evidence, reduce analyzers, calculate a market hypothesis,
change risk, place trades, or influence PAPER certification.

## Separation from B3

The existing B3 persistence and journal modules remain frozen and unchanged.

Shadow-result storage is separate because B3 is specifically typed around
`MarketSnapshotV1`.

This module reuses B3 design invariants without changing or widening the B3
public APIs.

## Record schema

The record schema is:

`BRAIN_SHADOW_RESULT_RECORD_V1`

Each record contains exactly:

- `record_schema_version`
- `shadow_result_schema_version`
- `shadow_result_sha256`
- `snapshot_sha256`
- `shadow_result_payload`

Unknown or missing keys fail closed.

## Result identity

The content identity is:

`ShadowBrainResultV1.shadow_result_sha256`

The result hash is derived from the result's deterministic canonical JSON.

A changed result field changes the content hash.

The persistence layer verifies the object's own canonical SHA-256 before
creating record bytes.

## Snapshot cross-binding

Every record contains the exact `snapshot_sha256` carried by the Shadow result.

The top-level record hash and the payload snapshot hash must agree.

Replay verifies the same cross-binding again.

The persistence layer does not look up or reinterpret the snapshot.

## Constructor revalidation

The persistence boundary does not trust a directly forged dataclass object.

Before serialization it re-runs the frozen constructors for:

- `ShadowHypothesisV1`
- `ShadowBrainResultV1`

This closes the `object.__new__` boundary and rejects states the canonical
contracts reject, including:

- hypothesis/result market mismatch
- unsupported hypothesis label
- invalid confidence
- overlapping evidence attribution buckets
- malformed or blank provenance
- naive timestamps
- invalid production coverage
- contradictory production completion
- duplicate metadata IDs
- true authority fields

The reconstructed object must remain exactly equal to the input object and
must preserve identical canonical JSON.

## Strict JSON

Replay uses strict JSON decoding.

The persistence boundary rejects:

- duplicate JSON object keys
- non-finite numeric constants
- invalid UTF-8
- unknown schema keys
- missing schema keys
- malformed primitive types
- schema drift

Booleans are not accepted as numeric substitutes.

## Replay integrity

Replay reconstructs:

- `ShadowHypothesisV1`
- `ShadowBrainResultV1`

Replay verifies:

- record schema
- result schema
- hypothesis schema
- declared result SHA-256
- reconstructed result SHA-256
- declared snapshot SHA-256
- payload snapshot SHA-256
- reconstructed snapshot SHA-256
- canonical JSON equality

A tampered record therefore fails closed.

## Partial and zero-coverage results

A valid partial Shadow result may be persisted.

A valid zero-coverage Shadow result may also be persisted.

Persistence does not convert incomplete evidence into neutral evidence and
does not require a directional hypothesis.

## Immutable publication

Persistence is immutable.

If the target path does not exist:

1. canonical bytes are written to a temporary file
2. the temporary file is flushed
3. `fsync` is performed
4. immutable publication uses a filesystem link

The implementation does not overwrite an existing target.

If an existing target has identical bytes, persistence is idempotent.

If an existing target has different bytes, persistence raises
`ShadowResultPersistenceConflictError`.

Concurrent publication follows the same rules:

- identical bytes are idempotent
- different bytes conflict
- temporary files are cleaned up

## Filesystem error normalization

Filesystem preparation and publication errors are normalized through the
Shadow persistence exception hierarchy.

This includes invalid parent-directory topology such as attempting to create a
child below a regular file.

## Zero-authority boundary

The persistence layer cannot persist a result carrying true Shadow authority.

All of the following must remain false:

- execution authority
- decision authority
- risk authority
- position authority
- certification authority

Persistence does not create new authority.

## No operational side effects

The module has no:

- FYERS imports
- Angel One imports
- broker imports
- market-data provider calls
- network fetches
- current-clock reads
- randomness
- PAPER orchestration
- certification-counter mutation
- order submission
- CALL/PUT mapping
- position sizing
- P&L policy
- win-rate policy

## No journal yet

This module persists one immutable Shadow result record.

It does not assign session journal slots, maintain manifests, enumerate
chronological results, or coordinate snapshot/result pairs.

Those responsibilities belong to the separate Shadow-result journal phase
after this persistence boundary is frozen.

## Frozen dependencies

Persistence V1 depends on the already-frozen:

- `ShadowHypothesisV1`
- `ShadowBrainResultV1`

It does not modify:

- B3 snapshot persistence
- B3 snapshot journal
- Shadow evidence eligibility policy
- Shadow reducer
- market hypothesis
- Shadow composer

## Non-goals

Persistence V1 does not perform:

- evidence evaluation
- market prediction
- confidence tuning
- strategy routing
- trade qualification
- strike selection
- risk sizing
- position management
- broker submission
- production PAPER wiring
- certification accounting
