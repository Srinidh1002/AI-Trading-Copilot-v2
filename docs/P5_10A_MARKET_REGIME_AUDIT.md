# P5-10A canonical market-regime repository audit and ownership design

## Outcome

No canonical market-regime subsystem currently exists. The smallest safe P5-10
design is a new, pure, paper-only regime evaluator for one canonical identity
which consumes already-evaluated typed results. It must not recalculate
indicators, reinterpret news, select a strategy, or decide a trade.

## Evidence matrix

| Area | Evidence | Classification | Inputs / outputs | Readiness and recommendation |
|---|---|---|---|---|
| Technical aggregate | `services/contracts/technical_intelligence_result_v1.py`, `services/technical_intelligence/aggregation.py` | Canonical/reusable | four timeframe evidence -> status, BULLISH/BEARISH/NEUTRAL/MIXED bias, strength, blockers/warnings | Consume only `TechnicalIntelligenceResultV1`; do not recalculate RSI/MACD/EMA/ADX/ATR/BB. |
| Technical pipeline | `services/technical_intelligence/pipeline.py` | Reusable with adaptation | supplied candles/quality -> technical aggregate | It contains an optional clock/default current time; P5-10 consumes output only. |
| Broader market | `BroaderMarketIntelligenceResultV1`, `services/broader_market_intelligence/*` | Canonical/reusable | cross-market, breadth, volatility -> bias/strength/confirmation/divergence | Consume aggregate only; do not separately consume breadth, correlation, or volatility. |
| Global/institutional/event | `ExternalMarketContextResultV1`, `services/external_context/*` | Canonical/reusable | child contexts -> direction/strength/risk/restriction | Consume aggregate only; never child strengths plus aggregate again. |
| Session | `MarketSessionValidationV1`, `services/market_session/validator.py` | Canonical/reusable boundary | timestamp/calendar -> analysis/preparation/execution permissions | Regime records session condition; session remains final calendar/open authority. |
| Data quality/freshness | `MarketDataQualityResultV1`, `services/data_quality/freshness.py` | Reusable with adaptation | evidence timestamps -> valid/stale/future/malformed | P5-10 should consume supplied quality results; no clock/freshness recalculation. |
| Legacy regime | `services/analysis/market_regime_engine.py`, `services/market_regime_engine.py`, `services/market_regime_analyzer.py` | Legacy reference only | mappings/indicators -> strings, score, confidence, reasons | Heuristic, mapping-shaped, no canonical identity/provenance; do not integrate. |
| Trend/momentum engines | `services/analysis/trend_engine.py`, `services/trend_engine.py`, indicator engines | Reusable only through technical aggregate | raw/mapping indicators -> trend/score | Avoid duplicate technical scoring. |
| VIX/volatility legacy | `services/analysis/vix_engine.py`, legacy market strength | Incomplete/provider-coupled | snapshot mappings -> score | P5-8 volatility context supersedes for P5-10. |
| Breadth/correlation legacy | `services/analysis/market_breadth_engine.py`, `correlation_engine.py` | Duplicated/reference | mappings -> score/signal | Do not consume alongside P5-8 aggregate. |
| Strategy regime use | `services/strategy_selector.py`, `strategy_engine.py`, `strategy_regime_performance.py` | Strategy-coupled | regime labels -> strategy/action shaping | Future consumer only; P5-10 must not choose strategies. |
| Decision/opportunity regime use | `services/decision*`, `services/trade_opportunity/*` | Decision-coupled | scores/confidence -> trade decisions | Explicitly outside P5-10. |
| Dashboard display | `dashboard/*`, `services/dashboard/*` | Runtime/display-coupled | mapping-shaped analysis | Future read-only consumer, not an owner. |
| Replay | `services/replay/*`, P5-8/P5-9 replay tests | Canonical/reusable | fixed fixtures -> deterministic comparisons | Add P5-10 four-index replay only after evaluator contract stabilizes. |
| AI/news/sentiment | `services/ai/*`, `services/news.py`, `analysis/news_sentiment_engine.py` | Unsafe/provider-coupled | narrative/provider output -> sentiment/score | Exclude from canonical regime. |
| Random/simulated | `services/testing/test_data_generator.py`, archive/research paths | Simulated/reference | generated data | Fixtures only, never production regime input. |

## Ownership design

P5-10 should own a single `MarketRegimeResultV1` and pure evaluator. Its inputs
should be one `TechnicalIntelligenceResultV1`, one
`BroaderMarketIntelligenceResultV1`, one `ExternalMarketContextResultV1`, one
`MarketSessionValidationV1`, and supplied quality/freshness result(s), all for
the same canonical identity and caller-supplied timestamp. Keep optional input
semantics explicit; no child evaluator or provider call belongs in P5-10.

Suggested regime vocabulary: `TRENDING_BULLISH`, `TRENDING_BEARISH`, `RANGING`,
`HIGH_VOLATILITY`, `COMPRESSION`, `MIXED`, `UNAVAILABLE`. Keep direction,
volatility, participation, external-risk, session, data-quality, confirmation,
contradictions, blockers, warnings, and strength as separate fields. A regime
label must not encode BUY/SELL, sizing, contract choice, or execution rights.

### Non-double-counting rules

- Technical owns indicator-derived trend/momentum only.
- P5-8 owns correlation, breadth, and volatility aggregation; P5-10 consumes
  its aggregate once.
- P5-9 owns global/institutional aggregation and event restriction; P5-10
  consumes its aggregate once and treats event risk as non-directional.
- Market-session owns exchange-open, holiday, special-session, and execution
  permission. P5-10 may expose its state but cannot override it.
- Quality/freshness owns stale/future/malformed classification.

## Proposed sequence

P5-10B: contract and policy audit/design; P5-10C: immutable regime result and
policy; P5-10D: pure evaluator; P5-10E: four-index/replay/isolation; P5-10F:
separate additive consumer audit for opportunity/decision integration.

## Explicit exclusions

No provider adapters, news/AI sentiment, raw indicator recomputation,
strategy selection, option selection, final decisions, portfolio/risk action,
or paper/live execution belongs to P5-10A or the initial regime subsystem.

## P5-10C1A policy ownership and weights

P5-10C1A hardened `MarketRegimePolicyV1` with controlled ownership of
TECHNICAL, BROADER_MARKET, EXTERNAL_CONTEXT, and MARKET_SESSION. Required
components are TECHNICAL and MARKET_SESSION; broader-market and external
context remain optional. Valid caller ordering is normalized canonically, while
duplicates, overlap, unknown names, and omitted components are rejected.

Outer aggregate weights are technical 0.60, broader-market 0.25, and external
context 0.15. They are finite, non-negative, need not sum to one, and are
normalized over usable components only by future P5-10H. MARKET_SESSION and
event risk have no directional weight. `component_weights` is read-only,
derived from those scalar fields, excludes MARKET_SESSION, and is not an
independent configuration source. P5-10E/F/G compatibility reads remain
preserved. Freshness hardening remains P5-10C1B; thresholds, penalties,
event/session behavior, and precedence remain P5-10C2. P5-10H remains
deferred. The focused P5-10C1A suite passed 13 tests.

## P5-10B implementation status

P5-10B added `services/contracts/canonical_market_regime_result_v1.py` with
`CanonicalMarketRegimeResultV1`, a paper-only immutable classification shape
for one canonical identity. It retains only the audit-approved aggregate
technical, broader-market, external-context, and market-session children;
there is no evaluator, policy, or runtime integration. Quality integration is
explicitly deferred because the repository has no single appropriate aggregate
quality result child. Direction, trend, volatility, market condition,
confirmation, and entry suitability remain separate controlled dimensions.

## P5-10C2A policy thresholds and penalties

### Strength thresholds

- `bullish_strength_threshold = 0.55`
- `strong_bullish_strength_threshold = 0.75`
- `bearish_strength_threshold = 0.55`
- `strong_bearish_strength_threshold = 0.75`
- Strong thresholds cannot be weaker than their normal thresholds.

### Confidence thresholds

- `minimum_regime_confidence = 0.50`
- `strong_regime_confidence_threshold = 0.75`
- Strong confidence cannot be weaker than minimum confidence.

### Entry suitability

- `caution_confidence_threshold = 0.50`
- `suitable_confidence_threshold = 0.70`
- Restrictions override confidence; no trade selection occurs here.

### Confirmation

- `minimum_confirmation_count = 1`
- Missing optional evidence is not neutral confirmation.

### Aggregate penalties

- `conflict_penalty = 0.20`
- `missing_optional_component_penalty = 0.05`
- `warning_penalty = 0.05`
- `partial_confirmation_penalty = 0.10`
- Aggregate penalties are applied at most once per aggregate condition, and
  child-local penalties must not be duplicated.

### Validation boundary

- Aggregate weights remain finite and non-negative with no upper bound.
- Thresholds and penalties are bounded to `[0, 1]`.
- Confirmation count is a non-negative integer.

### Compatibility

Existing `range_bound_strength_max`, `directional_strength_min`,
`strong_directional_strength_min`, `confirmation_strength_threshold`,
`partial_confirmation_strength_threshold`, child-local conflict penalties, and
`partial_evidence_penalty` are retained unchanged; no duplicate compatibility
property is introduced. P5-10E/F/G evaluator behavior, P5-10C1A
ownership/weights, and P5-10C1B freshness remain unchanged.

### Tests

`tests/test_p5_10c2a_policy_thresholds_penalties.py` covers this policy-only
hardening. Test execution is not claimed here.

### Deferred work

- P5-10C2B volatility override policy remains pending.
- P5-10C2C event/session restrictions and status precedence remain pending.
- CanonicalMarketRegimeResultV1 hardening remains pending.
- P5-10H remains deferred.

## P5-10C2B policy volatility overrides

- `high_volatility_override_states = ("HIGH", "EXTREME")` is the sole
  configurable and serialized override-state source.
- Broader-market/P5-8 owns authoritative canonical volatility; technical
  volatility is not double-counted.
- The override is non-directional. Existing high/extreme confidence penalties
  remain distinct confidence modifiers.
- No VIX or indicator calculation occurs in the policy.
- Coverage is in `tests/test_p5_10c2b_policy_volatility_overrides.py`.
- P5-10C2C, result hardening, and P5-10H remain deferred.

## P5-10C2C policy event, session, and precedence

### Event overrides

- `event_risk_override_states = ("HIGH", "EXTREME")`
- `blocking_event_risk_states = ("EXTREME",)`
- Event risk is non-directional; blocking states must be a subset of override
  states. The policy stores states only.

### Session/fail-closed flags

- `block_when_analysis_disallowed = True`
- `preserve_session_owned_restriction = True`
- `use_most_restrictive_entry_policy = True`
- `block_on_required_component_failure = True`
- `warn_on_optional_component_failure = True`

`MarketSessionValidationV1` owns session state and external context owns event
restriction. `SESSION_OWNED` is preserved, the stricter restriction wins, and
entries may be blocked while analysis remains allowed. The policy performs no
clock or calendar checks.

### Status precedence

1. `BLOCKED`
2. `EVENT_RISK`
3. `CONFLICTING`
4. `HIGH_VOLATILITY`
5. `UNAVAILABLE`
6. `DIRECTIONAL`

The policy stores precedence only; secondary dimensions remain visible under
overrides and no regime classification occurs here.

### Compatibility

Existing evaluator reads are preserved and no child evaluator formula changed.
Earlier P5-10C policy behavior is unchanged; input and result contracts remain
untouched.

### Tests

`tests/test_p5_10c2c_policy_event_session_precedence.py` covers this policy
hardening. Test execution is not claimed here.

### Deferred work

- CanonicalMarketRegimeResultV1 hardening remains pending.
- P5-10H remains deferred.

## P5-10D canonical result compatibility hardening

`services/contracts/canonical_market_regime_result_v1.py` now represents the
complete future canonical aggregate shape without adding an evaluator. It adds
exactly typed optional technical, broader-market, external-context, and
market-session component references, with identity matching and partial or
all-absent references supported where status coherence permits it.

The primary-regime vocabulary covers strong/normal bullish and bearish,
range-bound, high-volatility, event-risk, conflicting, unavailable, and
blocked states. Separate controlled dimension vocabularies retain trend,
volatility, breadth, confirmation, entry suitability, event risk, and entry
restriction. Context status remains READY, READY_WITH_WARNINGS, CONFLICTING,
UNAVAILABLE, or BLOCKED.

Strength and confidence are finite `[0, 1]` values. The contract validates
identity and exact child types, status/primary coherence, event/high-volatility
override representation, session/entry restrictions, and PAPER-only
execution. It serializes timestamps and child references deterministically;
metadata and source timestamps are immutable and JSON-safe.

Coverage is in `tests/test_p5_10d_result_compatibility_hardening.py`.
P5-10H remains deferred until this suite passes.

## P5-10H1 deterministic canonical aggregation

`services/market_regime/aggregate.py` provides the pure
`aggregate_market_regime(market_regime_input, policy=DEFAULT_MARKET_REGIME_POLICY)`
function. It consumes required technical/session and optional broader/external
normalized components, evaluates supplied-timestamp freshness, and produces a
PAPER-only canonical result with deterministic ID, timestamp, evidence, and
metadata.

Directional strength and confidence use usable outer-weighted component values
only. Aggregate conflict, missing-optional, warning, and partial-confirmation
penalties apply at most once. Trend is technical-owned; volatility and breadth
are broader-market-owned; event risk and event restriction are external-owned;
session remains non-directional and owns analysis/entry boundaries. Precedence
is BLOCKED, EVENT_RISK, CONFLICTING, HIGH_VOLATILITY, UNAVAILABLE, then
directional classification.

The evaluator is isolated from providers, clocks, runtime integration, and
execution. Coverage is in `tests/test_p5_10h1_market_regime_aggregation.py`
and `tests/test_p5_10h1_market_regime_aggregation_isolation.py`. P5-10I
integration, P5-10J four-market replay, and P5-10K certification remain
pending; test execution is not claimed here.

## P5-10K final certification

### Certified scope

P5-10B canonical input, P5-10C policy, P5-10D canonical result, P5-10E
technical component, P5-10F broader-market component, P5-10G external-context
component, P5-10H aggregation, P5-10I isolated integration, and P5-10J
four-market replay are covered by `tests/test_p5_10k_certification.py`.

### Architecture boundary

The scope is normalized contracts and deterministic evaluators only: no
provider fetching, runtime/dashboard/decision/ranking/strategy/risk/portfolio
integration, or broker/execution integration. Results are PAPER-only with
`live_execution_eligible=False`.

### Market coverage

NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE are certification
targets.

### Certification tests

Final pass counts are **PENDING USER EXECUTION** for: (1) the P5-10K focused
test, (2) the complete P5-10 focused/regression set, (3) the relevant P5-8/P5-9
regression set, and (4) the complete repository suite.

### Repository tracking

All intended P5-10 implementation, test, fixture, and documentation files
must be tracked or staged before final certification. Untracked files are not
visible in ordinary `git diff --stat`; `git status --short` is the authoritative
pre-commit inventory check.

### Final certification status

P5-10K status: PENDING FINAL USER TEST OUTPUTS AND TRACKING VERIFICATION

## P5-10I isolated integration

`services/market_regime/service.py` exposes
`evaluate_market_regime(market_regime_input, policy=DEFAULT_MARKET_REGIME_POLICY)`.
It accepts only exact `MarketRegimeInputV1` and `MarketRegimePolicyV1` values,
delegates to `aggregate_market_regime` exactly once, and returns the canonical
result unchanged. Normalized child components are never reevaluated.

The function is exported from `services.market_regime`, preserves deterministic
provenance, and adds no provider/runtime, trade-selection, or execution
behavior. Its isolation boundary is covered by
`tests/test_p5_10i_market_regime_integration.py` and
`tests/test_p5_10i_market_regime_integration_isolation.py`. P5-10J four-market
replay and P5-10K certification remain pending; test execution is not claimed.

## P5-10J deterministic four-market replay

`tests/test_p5_10j_four_market_replay.py` and
`tests/test_p5_10j_four_market_replay_isolation.py` replay fixed NIFTY,
BANKNIFTY, FINNIFTY, and SENSEX inputs through the isolated public API. Cases
cover directional outcomes, blocked/event/conflict/high-volatility/unavailable
precedence, optional warnings, restrictions, freshness boundaries, and policy
weight/confirmation variants. They assert deterministic provenance and
serialization plus cross-market invariance, without provider or runtime
integration. Results remain PAPER-only. P5-10K certification remains pending.
### Final execution results

- P5-10K focused certification: 9 passed in 0.20s
- Complete P5-10 focused/regression boundary: 490 passed in 2.58s
- P5-8/P5-9 regression boundary: 387 passed in 25.04s
- Complete repository suite: 12,415 passed, 2 warnings in 66.39s

The two repository-wide warnings are existing warnings and no new P5-10
certification failure was reported.

### Repository tracking

All intended P5-8, P5-9, and P5-10 implementation, contract, evaluator,
fixture, test, and audit files must be staged or tracked before final
certification.

### Final certification status

P5-10K status: TEST BOUNDARIES PASSED — PENDING TRACKING VERIFICATION