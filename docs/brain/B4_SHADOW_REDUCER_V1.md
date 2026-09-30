# B4 Shadow Reducer V1

## Purpose

`shadow_reducer_v1` is the deterministic, zero-authority reduction layer
between the frozen B4 evidence-eligibility policy and the future market-level
Shadow Brain hypothesis evaluator.

The hierarchy is:

`Evidence -> Analyzer -> Category -> Market`

This module implements only the first two reduction boundaries:

`Evidence -> Analyzer -> Category`

It does not implement the market-level hypothesis formula.

## Frozen aggregation unit

The final market aggregation unit selected in B4 Step 3B is the category.

Evidence is not allowed to vote directly at market level because analyzers may
emit different numbers of evidence rows.

Analyzers are not allowed to vote directly at market level because the index
PREMARKET category has two production analyzers while other categories usually
have one.

The reducer therefore guarantees that an analyzer contributes at most one
state and a category contributes at most one state.

## Analyzer states

The analyzer reducer preserves these states:

- `BULLISH`
- `BEARISH`
- `NON_DIRECTIONAL`
- `UNKNOWN`
- `CONFLICT`

Opposing directional evidence is never silently converted to neutral.

Unknown, stale, unavailable, degraded or unverified evidence is governed by the
frozen eligibility policy before reduction.

## Category states

The category reducer preserves:

- `BULLISH`
- `BEARISH`
- `NON_DIRECTIONAL`
- `UNKNOWN`
- `CONFLICT`
- `MISSING`

Missing analyzers remain explicit.

A partially covered category may retain an observed directional state while
`coverage_complete=False` and while the missing analyzer IDs remain explicit.

## Registry binding

Analyzer identity is bound to the frozen production analyzer registry.

A direct `AnalyzerReductionV1` constructor cannot invent an analyzer or assign a
registered analyzer to the wrong category.

Category expectations are also bound to the frozen production registry.

`reduce_category_v1` does not accept caller-supplied expected analyzer IDs.
Therefore a caller cannot make an incomplete category appear complete by
overriding the registry expectation.

For example, NIFTY PREMARKET requires both:

- `index.gap.legacy_v1`
- `index.previous_session.legacy_v1`

If only one is present, the missing analyzer stays explicit and
`coverage_complete=False`.

## Weighting policy

There are no:

- category weights
- analyzer weights
- majority-vote rules
- P&L-derived weights
- win-rate-derived weights
- market-direction thresholds
- confidence formulas

Same-side duplicated evidence cannot create accidental extra market weight.

## PCR semantics

The reducer consumes the standardized evidence direction produced upstream.

It does not reinterpret raw PCR values.

Therefore index `PCR` and MCX `STABLE_PCR` retain their distinct upstream
semantics.

## Authority boundary

This module has no:

- production decision authority
- execution authority
- broker authority
- risk authority
- position authority
- certification authority

It produces immutable shadow reduction objects only.

## Production isolation

The current PAPER trading paths do not import this reducer.

B4 remains shadow-only until a later explicitly controlled integration phase.

## Next boundary

A later B4 step may consume category reductions to produce a deterministic
market-level shadow hypothesis.

That later step must define ties, conflict handling, missing coverage,
insufficient evidence and any confidence representation without tuning from
P&L or certification results.
