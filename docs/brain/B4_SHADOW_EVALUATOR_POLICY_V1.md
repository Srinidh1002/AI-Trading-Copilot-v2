# B4 Shadow Evidence Evaluator Policy V1

## Purpose

This policy is the deterministic eligibility boundary between frozen B2/B3 evidence and the future B4 Shadow Brain evaluator.

It does not aggregate a market hypothesis, calculate a trading score, choose a trade, size risk, place orders, manage positions, or affect PAPER certification.

## Input contracts

The policy consumes only:

- EvidenceV1;
- AnalyzerResultV1.

The future Shadow evaluator will receive these through the frozen MarketSnapshotV1 boundary.

## Directional eligibility

Evidence may participate directionally only when both conditions are true:

1. evidence status is AVAILABLE;
2. freshness is FRESH.

The policy then consumes only the already-standardized EvidenceV1 direction.

BULLISH remains BULLISH and BEARISH remains BEARISH.

NEUTRAL and MIXED are classified as NON_DIRECTIONAL.

UNKNOWN is classified as UNKNOWN.

## Fail-closed states

The following evidence statuses cannot contribute a directional vote:

- DEGRADED;
- UNVERIFIED;
- UNAVAILABLE.

The following freshness states cannot contribute a directional vote:

- STALE;
- UNKNOWN;
- NOT_APPLICABLE.

NOT_APPLICABLE exists in the frozen EvidenceV1 vocabulary, but B4 V1 intentionally fails closed because the current B2 source-adapter evidence path does not establish it as a directional freshness state.

## Analyzer status

AnalyzerResultV1 status OK is evaluable.

AnalyzerResultV1 status PARTIAL is also evaluable, but each contained EvidenceV1 item is independently subjected to the status, freshness and direction policy above.

Analyzer statuses ERROR and UNAVAILABLE force contained evidence to UNKNOWN for Shadow evaluation.

## source_authoritative

EvidenceV1 source_authoritative is preserved as provenance metadata.

B4 V1 does not use source_authoritative as a directional eligibility gate.

This avoids inventing an authority meaning beyond the frozen evidence contract while retaining the field for later attribution, auditing and policy research.

## Raw-value independence

The policy does not inspect:

- feature;
- value;
- unit;
- metadata;
- strength;
- confidence;
- quality_score;
- source.

Therefore it does not introduce feature-specific thresholds or reinterpret source outputs.

In particular, index PCR and MCX STABLE_PCR remain semantically distinct upstream. The policy consumes only their already-adapted direction.

## Determinism

Evidence classification depends only on:

- evidence status;
- evidence freshness;
- evidence direction;
- analyzer result status.

Analyzer classifications are returned in deterministic evidence-ID order.

## Explicit non-goals

This policy contains no:

- hypothesis aggregation;
- analyzer weighting;
- category weighting;
- confidence formula;
- scoring threshold;
- P&L input;
- win-rate input;
- strategy optimization;
- CALL or PUT mapping;
- strike selection;
- quantity calculation;
- stop-loss or target calculation.

## Authority boundary

The policy has no provider, broker, execution, risk, position, persistence, or certification authority.

It is not wired into the current R2.2 PAPER decision path.

## Certification isolation

The active R2.2 PAPER campaign remains unchanged.

When a materially changed Brain eventually becomes authoritative, it must begin under a distinct policy epoch and cannot inherit certification from older strategy behavior.

## Next step

After this policy is frozen, B4 may define deterministic hypothesis aggregation over policy-classified evidence.

That later aggregation must remain zero-authority and must not be selected or tuned from PAPER P&L.
