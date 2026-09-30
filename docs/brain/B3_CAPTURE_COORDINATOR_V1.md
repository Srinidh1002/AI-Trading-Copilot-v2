# B3 Capture Coordinator V1

## Purpose

Capture Coordinator V1 is the zero-authority boundary that turns already-produced
runtime source values into deterministic Brain evidence snapshots.

It does not fetch market data and it does not participate in trading decisions.

The flow is:

existing runtime source values -> frozen B2 adapters -> MarketSnapshotV1 ->
frozen B3 snapshot journal -> CaptureResultV1 read model.

## Supported markets

Index capture:

- NIFTY
- SENSEX

MCX capture:

- CRUDEOILM
- GOLDM
- NATGASMINI

## Input boundary

The coordinator accepts typed source objects that have already been produced by
existing engines.

It does not call FYERS, SmartAPI, HTTP providers, broker APIs or execution APIs.

IndexCaptureSourcesV1 can carry:

- premarket evidence;
- news evidence;
- technical evidence;
- breadth evidence;
- option-chain evidence.

McxCaptureSourcesV1 can carry:

- native MCX evidence;
- MCX event-risk evidence.

At least one source must be supplied.

## Partial evidence

The coordinator does not fabricate missing analyzers.

A partial source bundle produces a partial MarketSnapshotV1 while preserving the
full registry-defined expected analyzer set and explicit missing-analyzer list.

This allows downstream shadow research to distinguish missing evidence from a
neutral signal.

## Market-family boundary

NIFTY and SENSEX can only use the index capture path.

CRUDEOILM, GOLDM and NATGASMINI can only use the MCX capture path.

A source whose market does not equal the requested capture market is rejected
before snapshot publication.

## PCR semantics

Index and MCX PCR semantics remain source-specific.

The index option-chain adapter preserves feature PCR and its legacy source
interpretation.

The MCX adapter preserves feature STABLE_PCR, raw_pcr metadata, stable PCR
direction and the MCX source interpretation.

The coordinator does not normalize one market family into the other.

## Event evidence

UNVERIFIED event evidence remains UNVERIFIED.

The coordinator cannot promote source authority and cannot convert an unverified
event source into a verified trading block.

## Source identity

Every snapshot preserves:

- source strategy version;
- source policy epoch;
- source runtime reference.

These identities survive journal persistence and deterministic replay.

## Time boundary

snapshot_at and generated_at must be timezone-aware.

Trading-session resolution is not inferred by this coordinator. The caller supplies
the canonical session_id used by the frozen journal.

## Capture semantics

The frozen journal provides:

- content-addressed records;
- atomic immutable timestamp slots;
- append-only manifest entries;
- identical-capture idempotency;
- same-slot different-hash rejection;
- deterministic offline replay.

The coordinator delegates storage semantics to that frozen journal rather than
reimplementing them.

## CaptureResultV1

The returned read model contains snapshot identity, journal identity, analyzer
coverage, missing analyzers, evidence-status counts, freshness counts and source
policy identity.

Its authority flags are permanently false for:

- execution;
- decision;
- risk;
- position management;
- certification.

## Production isolation

Capture Coordinator V1 is not wired into run_nifty.py, run_sensex.py, MCX
production decision paths, paper execution or the R2.2 supervisor.

The active R2.2 PAPER certification campaign therefore remains behaviorally
unchanged.

## B3 boundary

With this component frozen, B3 provides deterministic standardized evidence,
MarketSnapshotV1 construction, immutable persistence, append-only journaling,
offline replay and isolated capture orchestration.

The next phase is B4: a zero-authority Shadow Brain that consumes these frozen
snapshots without controlling the live PAPER decision path.
