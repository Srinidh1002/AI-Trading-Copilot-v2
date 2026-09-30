# B4 Shadow Composer V1

## Purpose

`shadow_composer_v1` is the pure deterministic composition boundary for
Shadow Brain V1.

It converts one immutable `MarketSnapshotV1` into one
`ShadowBrainResultV1`.

The frozen composition hierarchy is:

`MarketSnapshotV1`
`-> production AnalyzerResultV1 inputs`
`-> AnalyzerReductionV1`
`-> CategoryReductionV1`
`-> ShadowHypothesisV1`
`-> ShadowBrainResultV1`

The composer is shadow-only and has no execution authority.

## Single input

The public function is:

`compose_shadow_brain_v1(snapshot)`

Its only input is `MarketSnapshotV1`.

The composer does not accept:

- provider clients
- broker clients
- account balances
- order objects
- P&L
- historical win rate
- trade action overrides
- current clock values
- random seeds

## Snapshot revalidation

The composer does not blindly trust a directly constructed dataclass instance.

Before evaluation it revalidates:

- `MarketSnapshotV1`
- every nested `AnalyzerResultV1`
- every nested `EvidenceV1`
- registry schema identity
- expected production analyzer identity
- analyzer registration
- analyzer versions
- evidence identity consistency
- evidence category against the frozen analyzer descriptor
- global evidence-ID uniqueness
- source provenance
- zero-authority constraints

This is required because Python dataclasses can be forged or reconstructed
outside the canonical snapshot builder.

## Provenance

The following snapshot provenance fields are mandatory for composition:

- `source_strategy_version`
- `source_policy_epoch`
- `source_runtime_ref`

They must be non-empty trimmed strings.

The composer does not normalize or rewrite these values.

It preserves them exactly in `ShadowBrainResultV1`.

A null, blank or malformed provenance value causes composition to fail closed.

## Frozen registry identity

The snapshot registry schema must exactly match the frozen analyzer registry.

`expected_production_analyzers` must exactly equal the production analyzers
registered for the snapshot market.

A caller cannot silently shrink or replace the expected production set.

## Production analyzers versus registered Shadow extras

Only analyzers whose frozen registry descriptors are currently consumed by
production may drive the V1 market hypothesis.

Registered Shadow-extra analyzers may exist in the same snapshot.

They:

- remain part of the snapshot hash
- remain visible to snapshot-global quality metadata
- do not enter production analyzer reduction
- do not change market category quorum
- do not change the V1 market hypothesis

This prevents experimental Shadow evidence from silently influencing the
production-baseline comparison.

## Evidence identity hardening

Nested evidence must remain consistent with its containing analyzer result and
the frozen analyzer registry.

The composer rejects evidence when:

- evidence market differs from analyzer-result market
- evidence analyzer differs from analyzer-result analyzer
- evidence analyzer version differs from analyzer-result version
- evidence category differs from the frozen analyzer descriptor

The composer also rejects:

- analyzer-result market different from snapshot market
- analyzer not registered for the snapshot market
- analyzer version drift
- duplicate analyzer IDs
- globally duplicated evidence IDs

The evidence-category guard applies to production analyzers and registered
Shadow-extra analyzers.

## Partial snapshots

`production_complete=True` is not required for composition.

Partial snapshots are intentionally evaluatable.

Missing production analyzers remain explicit through:

- `production_coverage_pct`
- `production_complete`
- `missing_production_analyzers`
- missing category reductions
- the market hypothesis quorum

A zero-coverage snapshot therefore remains a valid deterministic Shadow input
and produces `INSUFFICIENT_EVIDENCE`.

It does not fabricate neutral evidence.

## Category quorum

Market direction remains category-based, not analyzer-count-based.

NIFTY and SENSEX currently contain ten expected categories even though there
are eleven production analyzers because PREMARKET contains two analyzers.

Those two PREMARKET analyzers cannot count as two market votes.

The previously frozen market rule remains:

- index directional/resolved threshold: 6 of 10 expected categories
- MCX directional/resolved threshold: 4 of 6 expected categories

The composer does not change this rule.

## Quality metadata

`unverified_evidence_ids` and `stale_evidence_ids` are derived from all
evidence inside the snapshot, including registered Shadow-extra analyzers.

The dimensions are independent.

An evidence ID may therefore legitimately appear in both sets when it is both:

- `status == UNVERIFIED`
- `freshness == STALE`

These metadata sets do not vote on market direction.

## Snapshot hash binding

The result copies the exact `snapshot.snapshot_sha256`.

Registered Shadow-extra evidence therefore changes the snapshot hash even when
it cannot influence the market hypothesis.

This preserves full reproducibility and auditability of the exact input used by
the Shadow evaluation.

## Replay determinism

For the same valid snapshot, composition is deterministic.

The composer performs no current-clock reads and uses no randomness.

`ShadowBrainResultV1.generated_at` comes from `snapshot.generated_at`.

A persisted snapshot replay therefore produces the same Shadow result as the
original snapshot.

## Authority boundary

All five Shadow result authority fields are fixed to `False`:

- execution authority
- decision authority
- risk authority
- position authority
- certification authority

A forged input snapshot with any authority set to true is rejected.

The composer cannot produce:

- CALL or PUT
- BUY or SELL
- strike selection
- position quantity
- stop loss
- targets
- broker orders
- execution requests

## External side effects

The composer performs no:

- FYERS calls
- Angel One calls
- broker calls
- network fetches
- filesystem snapshot reads
- persistence writes
- journal writes
- runtime orchestration
- PAPER certification mutation

Data capture and replay remain separate B3 responsibilities.

## Frozen dependencies

Composer V1 reuses the already-frozen:

- evidence contracts
- analyzer registry
- MarketSnapshotV1
- evidence eligibility policy
- analyzer reducer
- category reducer
- market hypothesis
- ShadowBrainResultV1 contract

It must not reinterpret those policies.

## Non-goals

Composer V1 deliberately contains no:

- category weights
- analyzer weights
- confidence model
- P&L optimization
- win-rate optimization
- strategy routing
- CALL/PUT mapping
- strike selection
- risk sizing
- position management
- broker submission
- production PAPER wiring

Those belong to later independently reviewed phases.
