# B2 Common Evidence Contracts V1

## Purpose

B2 begins the isolated Brain architecture without changing the running R2.2
PAPER policy.

The existing five-market system currently has multiple production analysis
families:

- NIFTY/SENSEX use the existing index runtime and legacy MTF path.
- MCX uses its product-native MTF, regime, structure, PCR, Price/OI and
  decision stack.
- The canonical `services/technical_intelligence` package exists and its
  indicator mathematics have been independently verified, but B1 showed that
  it is not currently the production-authoritative technical path.

B2 therefore standardizes **evidence contracts first**. It does not replace
existing engines.

## New contracts

### EvidenceV1

Represents one normalized observation.

Required semantics include:

- market
- analyzer and analyzer version
- category and feature name
- observation and generation timestamps
- availability status
- freshness status
- source
- optional scalar value/unit
- normalized direction
- strength/confidence/quality
- source-authority flag
- explicit unavailable reason
- blockers, warnings and JSON-safe metadata

### AnalyzerResultV1

Groups evidence emitted by one analyzer.

It validates that all evidence:

- belongs to the same market;
- belongs to the same analyzer/version;
- has unique evidence IDs.

## Zero-authority invariant

`AnalyzerResultV1.execution_authority` is permanently `False`.

B2 contracts therefore cannot:

- create an order;
- select BUY_CALL or BUY_PUT;
- override data-quality blockers;
- override risk;
- increment certification;
- modify a live position;
- alter the current R2.2 policy.

## Why this comes before a Brain

The current system contains multiple engine families with different field
names and semantics. A future Brain must not consume them through ad-hoc
dictionary access.

Adapters will translate the existing outputs into these contracts while the
existing production engines remain authoritative.

Later phases will add:

1. analyzer registry;
2. zero-authority adapters;
3. deterministic market snapshots and replay;
4. Shadow Brain;
5. centralized risk;
6. authoritative event intelligence;
7. policy routing and five-market ranking;
8. position intelligence;
9. attribution/calibration/drift;
10. a new forward PAPER epoch for any materially changed policy.

No historical certification trade will automatically certify a changed Brain.