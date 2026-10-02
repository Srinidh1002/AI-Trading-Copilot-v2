# X4 Phase B4 — offline historical replay and provenance sidecar

**Scope:** Deterministic research-only replay of the frozen X4 A/B1/B2/B3
contracts. This phase adds `replay_provenance_v1.py`; it does not modify the
frozen B1–B4 Brain, the X1–X3 source, the FYERS SDK facade, existing PAPER
execution, certification counters, or production runtime composition.

## Inputs and point-in-time safeguards

- Input is a previously captured normalized FYERS futures-candle archive,
  not a live endpoint or broker session. Its ordered rows are copied into
  immutable mappings and their SHA256 is checked against a declared archive
  fingerprint. The archive records a source archive ID, capture ID, acquisition
  time, canonical IST session, timeframe, and **separate proof references** for
  capture, session, candle-start semantics, and price units.
- Volume-unit, OI-unit, and OI-timestamp proof references are independently
  optional. Their absence keeps the corresponding X4 metrics unavailable;
  nonempty numeric fields alone are not evidence of verified units or timing.
- Candle starts must be strictly contiguous at the declared interval, belong
  to the same IST session date, and describe bars completed before archive
  acquisition. Gaps, duplicate/out-of-order bars, mixed sessions, reused
  capture IDs, and changed archived bytes are rejected, not interpolated.
- For each historical `as_of`, only candle rows whose **entire bar** closed by
  that checkpoint are sent through the existing B1 adapter. An archive
  downloaded retrospectively can be used for simulation, but its later
  acquisition is marked explicitly; it is not proof the exact data were
  available to the provider at the earlier simulated time.
- The canonical futures resolution must predate the earliest requested
  checkpoint. The B1 and B2 contract, session, expiry, quality and freshness
  guards remain in force; this module does not bypass them.
- The required timeframes must be explicitly declared, together with each
  timeframe's freshness budget. Missing closed-bar prefixes become missing
  timeframes in the existing B2/B3 outputs, not fabricated or forward-filled
  observations.

## Basis provenance limitation

A basis reference requires a separate nonempty proof identifier and must not
have been observed after the replay checkpoint. The replay checkpoint records
both `basis_reference_sha256` and `basis_proof_id` alongside the B2 source
result hash and B3 research-view hash. B3's per-feature dependency list does
**not yet include a cryptographic link to the benchmark itself**; this
separate sidecar must be preserved alongside the research output. It is not
an externally authenticated signature of the benchmark.

## Verification boundaries

**The offline module checks structural and hash consistency of supplied proof
identifiers. It cannot independently authenticate those identifiers, validate
real FYERS documentation, determine the provider's physical OI/volume units,
confirm whether historical OI had the same timestamp semantics as the candle,
or prove that an archived value was observable at an earlier historical
checkpoint.** Accordingly, every result sets
`real_provider_semantics_proven=False` and records an explicit blocker.
Separately acquired primary-provider evidence and a documented review are
required before any real provider verification can be asserted.

Hash linkage provides content integrity only relative to the supplied archive;
it is not external authenticity, an exchange certification, or proof of
absence of survivorship bias. The checkpoint is `data_only=True`,
`independent_vote=False`, `certification_eligible=False`, and every risk,
position, execution, and live-trading authority flag is false.

Replay results and research projections **never count toward the 100 valid
live-origin, executed, closed and reconciled PAPER trades per market**. They
are not trading signals, training labels, promises of profitability, or
approval for any use of real capital.

## Test scope

The B4 test module covers all five markets; early versus late checkpoint
prefixes; later-bar changes not affecting earlier computed results; missing
OI or volume proofs; gaps, duplicates, out-of-order observations, mixed
sessions, capture-ID collisions, invalid archive hashes, future-dated
instrument resolution, future-dated spot benchmarks, missing data, nested
immutability, deterministic research hashes, and all-zero trading authority.

## Remaining gates

- B5: full selected Brain/X1–X4 regression, independent authority/import
  audit, provenance document review, specific real-provider capture review,
  and the scoped source/test/documentation freeze.
- X9: canonical MarketSnapshotV2 registration.
- X10: explicit hierarchical evidence reduction with correlated feature
  groups; no automatic promotion of X4 research metrics into trade votes.
- The production PAPER policy and any later live-capital eligibility remain
  separate manual decisions with their own evidence and certification gates.
