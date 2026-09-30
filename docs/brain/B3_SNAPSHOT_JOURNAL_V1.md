# B3 Snapshot Journal V1

## Purpose

B3 Step 3 organizes immutable MarketSnapshotV1 records into deterministic
market/session journals for offline replay and future shadow analysis.

It remains independent from the running R2.2 PAPER runtime.

## Deterministic layout

Each market/session contains three logical stores:

- records/<snapshot-sha256>.json
- slots/<utc-capture-slot>.json
- manifest/<utc-capture-slot>_<snapshot-sha256>.json

Snapshot records use the frozen B3 Step 2 self-verifying persistence format.

## Content-addressed records

The snapshot SHA-256 determines its record filename.

Identical records are idempotent. Conflicting immutable content is rejected.

## Capture slots

A market/session/timestamp slot can identify only one snapshot hash.

Slot publication uses atomic no-overwrite semantics.

A same-slot different-hash capture therefore fails closed rather than replacing
the already-published slot.

## Append-only manifest

The manifest is a directory of immutable entries rather than one mutable JSONL
file. This avoids a shared append race.

Each manifest entry contains:

- market and session identity;
- snapshot timestamp;
- snapshot SHA-256;
- deterministic record path;
- source strategy version;
- source policy epoch;
- source runtime reference;
- permanently-false authority fields;
- its own canonical entry SHA-256.

## Capture order

Capture publishes in this order:

1. content-addressed snapshot record;
2. immutable timestamp slot;
3. immutable manifest entry.

The manifest is published last.

A crash before manifest publication cannot falsely advertise a completed logical
journal entry.

## Verification

Journal enumeration verifies manifest schema, manifest self-hash, deterministic
filenames, deterministic record paths, slot correspondence, referenced snapshot
existence and full B3 Step 2 replay integrity.

It also verifies market, timestamp, strategy version, policy epoch and runtime
reference against the replayed snapshot.

## Chronology

Logical enumeration is sorted by snapshot timestamp and then snapshot SHA-256.

Filesystem enumeration order is never treated as authoritative.

## Session identity

session_id is explicitly supplied and validated as canonical YYYY-MM-DD.

B3 Step 3 does not infer an exchange session from a UTC timestamp. Session and
exchange-calendar resolution belongs to the future capture coordinator.

## Orphan artifacts

A failed or losing capture can leave an unreferenced content-addressed record or
a slot without a manifest entry.

Neither artifact becomes part of logical journal replay because the manifest is
the authoritative index.

B3 Step 3 does not delete evidence.

## Authority boundary

The journal provides no execution, decision, risk, position-management, broker
or certification authority.

Offline replay performs no FYERS, SmartAPI, HTTP or broker calls.

## Production isolation

The journal is not imported by NIFTY, SENSEX, MCX, execution or supervisor
production paths.

The active R2.2 PAPER certification campaign remains untouched.

## Next step

After this format is frozen, B3 Step 4 will build an isolated capture
coordinator/read model that accepts already-produced source values, invokes the
B2 adapters, creates MarketSnapshotV1, and persists it through this journal.

Only after deterministic capture/storage/replay is proven will B4 Shadow Brain
consume these snapshots.
