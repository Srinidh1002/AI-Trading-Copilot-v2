# B4 Shadow Market Hypothesis V1

## Purpose

`shadow_market_hypothesis_v1` is the deterministic zero-authority
Category-to-Market layer of Shadow Brain V1.

The frozen hierarchy is:

`Evidence -> Analyzer -> Category -> Market`

The evidence, analyzer and category semantics are owned by the already-frozen
B4 contracts, evidence policy and reducer. This module does not reinterpret raw
market values.

## Decision input

The market hypothesis is selected from `CategoryReductionV1.state` values only.

`AnalyzerReductionV1` objects are supplied only so the final hypothesis can
retain evidence attribution.

Analyzer count, evidence count and evidence multiplicity cannot change the
market hypothesis.

Each category contributes at most one market-level state.

## Expected categories

Expected categories are derived from the frozen production analyzer registry.

NIFTY and SENSEX currently have ten expected categories.

CRUDEOILM, GOLDM and NATGASMINI currently have six expected categories.

The implementation therefore uses proportional strict-majority semantics
instead of one shared raw count across all markets.

## Resolved and unresolved states

Resolved category states are:

- `BULLISH`
- `BEARISH`
- `NON_DIRECTIONAL`

Unresolved category states are:

- `CONFLICT`
- `UNKNOWN`
- `MISSING`

`CONFLICT`, `UNKNOWN` and `MISSING` are not silently converted to neutral.

They are also not global vetoes.

## Market hypothesis rule

A market is `BULLISH` only when BULLISH categories are strictly more than half
of all expected categories.

A market is `BEARISH` only when BEARISH categories are strictly more than half
of all expected categories.

If neither directional majority exists, the market is `NEUTRAL` only when the
number of resolved categories is strictly more than half of all expected
categories.

Otherwise the market is `INSUFFICIENT_EVIDENCE`.

Current derived boundaries are therefore:

- NIFTY/SENSEX: 6 of 10 for directional majority or resolved quorum.
- MCX markets: 4 of 6 for directional majority or resolved quorum.

There are no category weights, importance rankings, majority rules based only
on available categories, or P&L-derived thresholds.

## Examples

For an index market:

- 6 BULLISH + 4 BEARISH -> `BULLISH`
- 5 BULLISH + 5 BEARISH -> `NEUTRAL`
- 6 BULLISH + 4 UNKNOWN -> `BULLISH`
- 5 BULLISH + 5 UNKNOWN -> `INSUFFICIENT_EVIDENCE`
- 6 NON_DIRECTIONAL + 4 UNKNOWN -> `NEUTRAL`

For an MCX market:

- 4 BULLISH + 2 BEARISH -> `BULLISH`
- 3 BULLISH + 3 BEARISH -> `NEUTRAL`
- 4 BULLISH + 2 UNKNOWN -> `BULLISH`
- 3 BULLISH + 3 UNKNOWN -> `INSUFFICIENT_EVIDENCE`

## Confidence V1

The frozen `ShadowHypothesisV1` contract requires a numeric confidence field.

Market Hypothesis V1 uses:

`confidence = 0.0`

as an explicit deferred sentinel.

It is not:

- a probability
- an estimated win rate
- a P&L score
- an execution threshold
- a category-coverage score

A future dedicated confidence policy may define a transparent confidence
representation. It must not reinterpret this V1 sentinel retroactively.

## Evidence attribution

Every observed evidence ID must remain visible in exactly one of the three
frozen `ShadowHypothesisV1` attribution buckets:

- `supporting_evidence_ids`
- `opposing_evidence_ids`
- `unknown_evidence_ids`

The three sets are disjoint and their union equals all observed evidence IDs
supplied by the present analyzer reductions.

For a BULLISH market hypothesis, bullish-category directional evidence supports
the hypothesis and bearish-category directional evidence opposes it.

For a BEARISH market hypothesis, bearish-category directional evidence supports
the hypothesis and bullish-category directional evidence opposes it.

For a NEUTRAL hypothesis, non-directional evidence supports neutrality while
directional evidence is opposing evidence.

For `INSUFFICIENT_EVIDENCE`, all observed evidence is retained in the unknown
attribution bucket because the market-level evidence quorum is insufficient to
assign market-level support or opposition.

## Meaning of residual unknown attribution

`unknown_evidence_ids` is an output-attribution bucket in
`ShadowHypothesisV1`.

When the final market hypothesis is directional, valid non-directional evidence
is neither directional support nor directional opposition. Because the frozen
Shadow hypothesis contract has no fourth contextual/non-directional attribution
bucket, that residual observed evidence is retained in `unknown_evidence_ids`.

This does not rewrite the upstream evidence direction to UNKNOWN.

The original EvidenceV1 and AnalyzerReductionV1 semantics remain unchanged.

The residual bucket exists only to guarantee complete and auditable market-level
attribution.

## Conflict handling

A CONFLICT category is unresolved for market quorum calculations.

Its observed evidence remains explicit in the unknown market-level attribution
bucket.

A conflict category does not automatically veto a directional market
hypothesis when the strict majority requirement is independently satisfied by
other expected categories.

## Registry and contract hardening

All market categories must exactly cover the frozen production category set for
that market.

All analyzer attribution objects must exactly match the analyzers declared
present by their corresponding category reductions.

Reducer objects are revalidated through their frozen constructors before use,
so forged category/analyzer identities or inconsistent states are rejected.

Evidence IDs must be globally unique across analyzer reductions.

## Rationale codes

The primary deterministic rationale codes are:

- `MARKET_BULLISH_EXPECTED_CATEGORY_MAJORITY`
- `MARKET_BEARISH_EXPECTED_CATEGORY_MAJORITY`
- `MARKET_RESOLVED_QUORUM_WITHOUT_DIRECTIONAL_MAJORITY`
- `MARKET_RESOLVED_QUORUM_NOT_MET`

Additional deterministic presence codes record:

- missing categories
- unknown categories
- conflict categories

Rationale codes do not depend on P&L or historical win rate.

## Authority boundary

Market Hypothesis V1 is shadow-only.

It has no:

- decision authority
- execution authority
- broker authority
- risk authority
- position authority
- certification authority

It does not produce:

- CALL or PUT
- BUY or SELL
- strike
- quantity
- stop loss
- target
- broker order

The current PAPER execution paths do not import this module.

## Frozen non-goals

This V1 layer deliberately contains no:

- category weighting
- analyzer weighting
- evidence weighting
- P&L optimization
- win-rate optimization
- confidence formula
- strategy routing
- strike selection
- risk sizing
- execution logic
- production wiring

Those are separate later phases and must not be smuggled into the market
hypothesis reducer.
