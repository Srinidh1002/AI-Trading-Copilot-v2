# B3 MarketSnapshotV1

## Purpose

`MarketSnapshotV1` is the first reproducible observation packet for the Brain
architecture.

The future Brain must consume a fixed evidence snapshot rather than reading
scattered mutable runtime dictionaries directly.

## Snapshot contents

A snapshot records:

- market;
- observation timestamp;
- generation timestamp;
- normalized analyzer results;
- the production analyzer set expected at capture time;
- analyzer-registry schema version;
- source strategy version;
- source policy epoch;
- optional source runtime reference.

## Capture-time expected analyzer set

The expected production analyzer IDs are stored inside the snapshot.

This matters because the analyzer registry can evolve later. Historical replay
must know what evidence was expected at the time the snapshot was created,
rather than silently applying a future registry definition.

## Coverage

The snapshot can report:

- expected production analyzer count;
- production analyzers present;
- missing production analyzers;
- registered shadow analyzers;
- production coverage percentage;
- whether the production evidence set is complete.

A shadow analyzer never fills a missing production analyzer slot.

## Evidence quality

The snapshot also derives counts for:

- AVAILABLE;
- DEGRADED;
- UNAVAILABLE;
- UNVERIFIED;

and freshness states such as:

- FRESH;
- STALE;
- UNKNOWN;
- NOT_APPLICABLE.

No quality state is silently upgraded.

## Deterministic identity

The canonical snapshot payload is serialized using deterministic JSON:

- sorted dictionary keys;
- compact separators;
- deterministic analyzer ordering;
- deterministic evidence ordering;
- deterministic blocker/warning ordering;
- non-finite JSON values forbidden.

The UTF-8 canonical JSON is hashed with SHA-256.

Identical snapshot content therefore produces the same digest even when
analyzer results were supplied in a different tuple order.

Any material evidence or capture-context change produces a different digest.

## Authority boundary

`MarketSnapshotV1` permanently has:

- execution_authority = False
- decision_authority = False
- risk_authority = False
- position_authority = False
- certification_authority = False

A snapshot is evidence, not a trade instruction.

## Production isolation

B3 Step 1 does not import MarketSnapshotV1 into:

- run_nifty.py;
- run_sensex.py;
- target_focused_bot.py;
- decision_composer.py;
- MCX paper runtime;
- automated paper supervisor.

The R2.2 PAPER campaign remains independent.

## Next step

B3 Step 2 will add deterministic persistence and replay verification.

The replay layer must:

1. write a self-verifying snapshot record;
2. restore the exact evidence packet;
3. recompute and verify SHA-256 identity;
4. detect tampering or truncation;
5. perform no provider calls;
6. have zero trading authority.

Only after snapshot/replay is proven should a Shadow Brain consume these
records.