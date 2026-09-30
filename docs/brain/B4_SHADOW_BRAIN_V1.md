# B4 Shadow Brain V1 — Output Contracts

## Scope

B4 Step 1 defines the immutable output boundary for the future Shadow Brain.

This step does not implement a scoring engine and does not participate in the
production PAPER decision path.

The contracts are analysis-only and consume the deterministic snapshot foundation
frozen in B3.

## Input boundary

The future Shadow Brain will consume MarketSnapshotV1 only.

It must not fetch FYERS data, call SmartAPI, access broker order APIs, or bypass
the B2/B3 evidence and snapshot boundaries.

## Supported markets

The contracts support exactly:

- NIFTY
- SENSEX
- CRUDEOILM
- GOLDM
- NATGASMINI

## ShadowHypothesisV1

ShadowHypothesisV1 represents a non-authoritative interpretation of snapshot
evidence.

The only allowed hypothesis labels are:

- BULLISH
- BEARISH
- NEUTRAL
- INSUFFICIENT_EVIDENCE

The contract records:

- market;
- confidence in the range 0.0 to 1.0;
- supporting evidence IDs;
- opposing evidence IDs;
- unknown evidence IDs;
- deterministic rationale codes.

Evidence-role collections must be sorted, unique and mutually disjoint.

These labels are research hypotheses. They are not CALL, PUT, BUY, SELL or order
instructions.

## ShadowBrainResultV1

The result envelope binds a hypothesis to the exact snapshot that produced it.

It preserves:

- market;
- snapshot SHA-256;
- snapshot timestamp;
- Shadow Brain generation timestamp;
- source strategy version;
- source policy epoch;
- source runtime reference;
- production analyzer coverage;
- missing production analyzers;
- unverified evidence IDs;
- stale evidence IDs;
- the immutable ShadowHypothesisV1.

## Explicit uncertainty

Missing, stale and unverified evidence remain explicit in the output contract.

The Shadow Brain must not silently convert unavailable or unverified evidence into
a neutral, bullish or bearish fact.

## Coverage integrity

A production_complete result requires exactly 100 percent production coverage and
no missing production analyzers.

An incomplete result requires coverage below 100 percent and at least one explicit
missing production analyzer.

## Determinism

ShadowBrainResultV1 has canonical compact sorted-key JSON serialization.

Its shadow_result_sha256 is the SHA-256 of that canonical UTF-8 JSON.

Equivalent results therefore produce identical canonical JSON and identical hashes.

A material output change changes the hash.

The hash is an integrity and reproducibility identifier. It is not a digital
signature or authenticity mechanism.

## Permanently forbidden authority

ShadowBrainResultV1 permanently sets all of the following to false:

- execution authority;
- decision authority;
- risk authority;
- position authority;
- certification authority.

Attempts to promote any of these flags are rejected.

## Deliberately absent trading fields

B4 V1 output contracts contain no:

- CALL or PUT action;
- BUY or SELL instruction;
- recommendation or production signal;
- strike;
- quantity;
- order;
- broker instruction;
- stop loss;
- target;
- P&L or profit field.

This prevents the contract itself from becoming an alternate execution API.

## P&L isolation

B4 V1 does not tune policy from PAPER P&L.

Outcome attribution and research belong to later explicitly separated research
phases. A changed Brain policy will require a distinct PAPER certification epoch.

## PCR semantics

B4 must preserve B2/B3 source semantics rather than normalizing them.

In particular:

- index option-chain PCR remains feature PCR with index-source interpretation;
- MCX PCR remains feature STABLE_PCR with MCX-source interpretation.

## Production isolation

These contracts are not imported by:

- run_nifty.py;
- run_sensex.py;
- index production decision paths;
- MCX production decision paths;
- PAPER execution;
- the R2.2 supervisor.

The active R2.2 PAPER certification campaign remains behaviorally unchanged.

## Next B4 construction step

After this contract boundary is frozen, the next B4 step will implement the
deterministic Shadow Brain evaluator.

That evaluator will:

1. consume MarketSnapshotV1 only;
2. classify available, unavailable, stale and unverified evidence;
3. preserve index and MCX source semantics;
4. produce one of the four hypothesis labels;
5. emit deterministic rationale codes and evidence IDs;
6. return ShadowBrainResultV1;
7. retain zero production authority.

It will remain isolated from the champion PAPER decision path.
