# X8-B4 — Frozen X2/X3 research-interface boundary

## Scope

Offline five-market Shadow research only. `bind_x3_technical_to_x8_v1` consumes
an *exact* frozen `X3MultiTimeframeResultV1`, its separately supplied SHA-256,
caller-declared availability time, and a positive freshness budget. It checks
market/instrument identity, timestamps, digest and basic constituent identity.
X3's aggregate `sha256` is a property. The X3 result has no independently
attested publication-time or publisher-authenticity proof, so a populated,
fresh X3 result is **UNVERIFIED**, not `AVAILABLE`. An empty MTF result is
`UNAVAILABLE`; an old populated result is `STALE`. The bridge does not reuse
individual indicators as independent votes or calculate a market regime.

`bind_x2_manifest_to_x8_v1` consumes an exact `X2FeatureManifestV1` and its
manifest digest for NIFTY or SENSEX. The manifest defines *what may be computed*,
not observed constituent returns, coverage, or source-available timestamps.
It is accordingly always `UNVERIFIED` as BREADTH research context, never
`AVAILABLE` empirical breadth. X2 is `UNAVAILABLE` for CRUDEOILM, GOLDM and
NATGASMINI; trying to attach an index manifest to MCX is rejected. A complete
measured X2 result adapter with raw-record availability/provenance remains
future work and is **not** inferred from this manifest.

Caller-declared availability is checked for time consistency but is **not** an
independent historical point-in-time attestation. This phase changes no frozen
X2, X3, X7 or earlier X8 source. No direction, scoring, strategy, execution,
portfolio, certification, market-open or capital authority is introduced.

## Verification

Focused adapter tests include all five X3 identities, both index manifests,
three unsupported MCX manifests, source-digest corruption, stale/future data,
wrong-market identities, invalid budgets and zero-authority invariants. The
isolated package uses explicit X2/X3 contract *test doubles* only because the
packaging fixture does not include the complete frozen X2/X3 dependency tree;
local full-repository regression is mandatory before acceptance. These tests
are not genuine X2/X3 integration certification.
