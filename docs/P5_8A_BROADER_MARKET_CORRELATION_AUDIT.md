# P5-8A broader-market and correlation audit

## 1. Executive summary

P5-7 is a suitable baseline for a new paper-only intelligence pillar. The repository has four canonical identities, immutable evidence/result contracts, provider-neutral freshness policy, multi-timeframe technical intelligence, option-chain intelligence, `TradeOpportunityV1`, and deterministic serialization. It has no canonical broader-market or correlation evidence.

Recommendation: build a pure supplied-evidence subsystem with separate pairwise cross-market, breadth, VIX-context, aggregate-result, and policy contracts. Their source cadence, identity cardinality, and availability rules differ, so consolidating them would make the result less precise. Providers/adapters remain outside the canonical packages. P5-8 produces evidence/warnings only: no decision, contract selection, capital reservation, or order effect.

## 2. Repository findings

| Area | Evidence | Classification | Consequence |
|---|---|---|---|
| Identity | `services/core/market_identity.py`: NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, SENSEX/BSE | Canonical | Reuse exactly; do not create another registry. |
| Universe | `MarketUniverseV1` preserves the four identities and order | Canonical | Use for deterministic ordering. |
| Quality/freshness | P5-2 contracts/policy expose aware timestamps, provenance, stale/future/incomplete states | Canonical | Consume quality-gated inputs; do not re-parse provider payloads. |
| MTF | P5-3 snapshot/quality/alignment packages use supplied canonical candles | Canonical | Supply completed, aligned related-index series. |
| Technical | P5-4 frozen result/policy conventions; 0..1 strength; unavailable weight unearned | Canonical | Follow vocabulary, immutability and no-look-ahead rules. |
| Option chain | P5-5 immutable metric/result patterns | Canonical | Broader evidence remains independent of options. |
| Opportunity | `TradeOpportunityV1` carries evidence IDs, blockers, contradictions, warnings | Canonical | Do not change it in P5-8A. |
| Observability | `AuditEventV1` has aware timestamps, JSON-safe attributes, semantic serialization | Canonical | Reuse later if an event is needed. |
| Regime/VIX | `market_regime_engine.py` and confidence code embed mapping/VIX thresholds | Compatibility | Reference only; no canonical P5-8 imports. |
| Correlation/breadth/VIX | `services/analysis/{correlation_engine,market_breadth_engine,vix_engine}.py` | Legacy/unsafe | Retain unchanged; no reuse. |
| Live candles | `market/live_multi_timeframe_data.py`, `historical_market.py` import broker/cache/pandas | Provider-coupled | Future adapter boundary only. |
| Dashboard/archive | Mapping-oriented dashboard/research paths | Legacy/reference | No P5-8 UI wiring. |

The terminology search also found retrospective anomaly/P&L correlation research. It is not contemporaneous market-index evidence and is not reusable here.

## 3. Reusable conventions and unsafe legacy code

Use `normalize_market_identity`, `SUPPORTED_MARKET_IDENTITIES`, P5-2 quality statuses, P5-3 alignment/completed-candle discipline, and P5-4/P5-5 dataclass conventions: `@dataclass(frozen=True, slots=True)`, standard library only, normalized controlled strings, finite bounded values, tuples, aware ISO timestamps, deterministic `to_json`, and `semantic_dict` without generated identity/time. Retain paper-only `execution_mode="PAPER"` and `live_execution_eligible=False`.

`MarketSnapshotV1` exposes optional India VIX value/status/timestamp, but it is a legacy-adapter-shaped mutable dataclass that imports pandas. It is an adapter/source reference, not an allowed canonical domain dependency. Canonical candle and P5-3 contracts are the appropriate boundary.

The legacy correlation engine computes NumPy correlation from lists without identity pairing, timestamp alignment, zero-variance handling, completed-candle guarding, provenance, freshness, or finite-result checks; it interprets correlation direction as a trade signal. The breadth engine converts absent counts to zero and uses `max(decline, 1)`; the VIX engine accepts a bare mapping value; market-strength aggregates them, risking double counting. All are unsafe for canonical reuse. No simulated/random broader-market engine was found.

## 4. Data availability matrix

| Input | Repository evidence | Classification | P5-8 treatment |
|---|---|---|---|
| Four identities | Core registry and universe | Available/canonical | Mandatory identity source |
| Four-index candles | Canonical candle/MTF contracts; legacy Angel fetchers, no audited four-index adapter | Contract available; acquisition unclear | Future adapter/provider verification |
| Related-index candles | No canonical NIFTY/SENSEX or BANKNIFTY/FINNIFTY feeder | Missing adapter | Supplied evidence only |
| India VIX | Optional `MarketSnapshotV1` value/status/time; legacy VIX mapping | Provider-coupled | Future provider-neutral adapter |
| A/D counts | Legacy breadth mapping only | Missing canonical source/provenance | New adapter/evidence |
| Breadth coverage/universe | No constituent/coverage contract found | Missing | Required for valid breadth |
| Constituents, weights, heavyweight contribution | No canonical data/calculation found | Missing | Optional/unavailable; never infer |
| Session/timestamps | P5-2/P5-3/session contracts | Available/canonical | Reuse gates |
| Portfolio exposure enforcement | Portfolio manager exists; no canonical four-index correlation control | Deferred to P8 | P5-8 warnings only |

No repository code proves provider support for BSE SENSEX candles, India VIX history/current update semantics, breadth, constituents, or index weights.

## 5. Recommended architecture

```text
services/contracts/
  cross_market_evidence_v1.py
  market_breadth_evidence_v1.py
  volatility_context_v1.py
  broader_market_intelligence_policy_v1.py
  broader_market_intelligence_result_v1.py
services/broader_market_intelligence/
  __init__.py
  correlation.py
  breadth.py
  volatility.py
  evaluator.py
  integration.py
```

Do not create `RelatedIndexEvidenceV1`: it is a `CrossMarketEvidenceV1` special case. Do not put raw candles, constituents, weights, provider payloads, narratives, or technical/option scores into these contracts. Initial policy relationships are ordered NIFTY/NSE↔SENSEX/BSE (`BROAD_MARKET_PEER`) and BANKNIFTY/NSE↔FINNIFTY/NSE (`SECTOR_PEER`). No implicit all-to-all matrix.

## 6. Detailed contract designs

### CrossMarketEvidenceV1 — necessary

Purpose: source-traceable pairwise descriptive relationship and current directional agreement; never a recommendation or causal assertion.

Required frozen fields: `evidence_id: str`, `created_at: datetime`, primary and related `symbol/exchange: str`, `relationship_type: str`, `timeframe: str`, `lookback_observations: int`, `sample_size: int`, `correlation_value: float | None`, `correlation_strength: str`, `primary_direction: str`, `related_direction: str`, `confirmation_state: str`, `divergence_state: str`, `freshness_status: str`, `source_ids: tuple[str, str]`, `source_timestamps: tuple[datetime, datetime]`, blockers and warnings. Optional aligned start/end timestamps must occur together. Fixed paper-only fields/schema apply.

Allowed values: relationship `BROAD_MARKET_PEER|SECTOR_PEER`; strength `UNAVAILABLE|WEAK|MODERATE|STRONG`; direction `BULLISH|BEARISH|NEUTRAL|UNAVAILABLE`; confirmation `CONFIRMED|NOT_CONFIRMED|UNAVAILABLE`; divergence `DIVERGENT|NOT_DIVERGENT|UNAVAILABLE`; freshness `VALID|VALID_WITH_WARNINGS|STALE|FUTURE|INCOMPLETE|MALFORMED|UNAVAILABLE`.

Normalize identities through the core registry and controlled values uppercase. Reject same/unsupported pair, blank duplicate sources, naive times, bools/non-finite values, correlation outside [-1,1], and sample size outside 0..lookback. Numeric correlation requires policy-minimum samples and no blocker. Unavailable/blocked means value is `None`, never invented 0; states are `UNAVAILABLE`. Mandatory stale/future/misaligned/zero-variance/insufficient data blocks; optional unavailable data can warn only under policy. Serialize aware timestamps, tuples as ordered lists; semantic form removes evidence ID/created time but retains sources/times.

### MarketBreadthEvidenceV1 — necessary

Purpose: scoped primary-index breadth including explicit A/D coverage and optional externally computed heavyweight state.

Required fields: `evidence_id`, `created_at`, primary identity, `breadth_scope`, `source_id`, `source_timestamp`, freshness status, `advance_count|None`, `decline_count|None`, `unchanged_count|None`, `eligible_count|None`, `observed_count|None`, `advance_decline_ratio|None`, `breadth_bias`, `breadth_strength: float`, `heavyweight_state`, blockers/warnings. Heavyweight source ID/time must be supplied together when state is not unavailable.

Scope is `INDEX_CONSTITUENTS|EXCHANGE_UNIVERSE`; bias is `BULLISH|BEARISH|NEUTRAL|UNAVAILABLE`; heavyweight state is `CONFIRMS|CONTRADICTS|NEUTRAL|UNAVAILABLE`. Counts are non-negative integers; observed <= eligible; counts sum to observed. Ratio is finite/non-negative and exists only where declines are positive—use `None`, not infinity, for zero declines. Strength is [0,1], exactly 0 if blocked/unavailable. Coverage is derived, not trusted input. Partial count sets/invalid coverage reject. Missing heavyweight is `UNAVAILABLE`, never neutral. Missing/insufficient mandatory breadth blocks; optional missing remains explicit. Serialization follows above conventions.

### VolatilityContextV1 — necessary

Purpose: source-provenanced India VIX context, not equity directional evidence.

Required fields: `context_id`, `created_at`, `source_id`, `source_timestamp`, `freshness_status`, `india_vix_value: float|None`, `vix_change_percent: float|None`, `vix_regime`, `volatility_direction`, `volatility_strength`, blockers/warnings. Regime: `LOW|NORMAL|ELEVATED|HIGH|EXTREME|UNAVAILABLE`; direction: `RISING|FALLING|STABLE|UNAVAILABLE`; strength [0,1]. VIX is positive/finite; change is finite and initially bounded to absolute 100% until source semantics are verified. Unknown/stale/invalid/absent VIX is unavailable (value/change None; strength 0), not normal. VIX should initially be optional/warning-only because no canonical source is proven. Same timestamp/freshness/paper/serialization rules apply.

### BroaderMarketIntelligenceResultV1 — necessary

Purpose: aggregate supplied pair/breadth/VIX evidence for one primary identity without creating an action, contract, or final confidence.

Required fields: `result_id`, `created_at`, primary identity, `policy_name`, `cross_market_evidence: tuple[CrossMarketEvidenceV1,...]`, `breadth_evidence: MarketBreadthEvidenceV1|None`, `volatility_context: VolatilityContextV1|None`, `intelligence_status`, `aggregate_bias`, `aggregate_strength`, confirmation/divergence states, blockers, contradictions, warnings, and sorted duplicate-free `source_timestamps: tuple[tuple[str,datetime],...]`. Status: `READY|READY_WITH_WARNINGS|INSUFFICIENT_DATA|STALE|FUTURE|CONFLICTING|UNSUPPORTED|FAILED`; bias: `BULLISH|BEARISH|NEUTRAL|MIXED|UNAVAILABLE`.

Each pair references primary identity once, obeys policy ordering, and is unique by related identity. Strength [0,1] is zero in blocking states and must not be renormalized upward for missing optional sources. Contradictions (for example, strong positive relationship plus opposing directions) are evidence facts, not causal claims. READY has no warnings/blockers/contradictions; warning-ready has no blockers; blocked statuses require blockers and unavailable/zero strength. Semantic serialization removes result ID/time recursively.

### BroaderMarketIntelligencePolicyV1 — necessary

Purpose: frozen evaluator configuration, never source data. Required fields: policy name; mandatory/optional ordered identity relationships; timeframe; minimum cross-market samples; moderate/strong/confirmation/divergence correlation thresholds; minimum/warning breadth coverage; bullish/bearish A/D thresholds; sorted VIX boundaries; maximum evidence age; future tolerance; missing/stale/contradiction behavior; score weights; session behavior; fixed execution fields/schema.

Validation: positive finite ages/sample count (minimum >=2); thresholds [0,1] and ordered; warning coverage <= minimum coverage; bearish ratio <1<bullish ratio; strictly increasing VIX boundaries; unique canonical pairs; weights [0,1] summing exactly 1; behavior in `BLOCK|WARN|ALLOW`. Policy owns thresholds/weights and nothing provider-specific. Candles, VIX, timestamps, counts, directions, weights, payload parsing, credentials, action thresholds, and exposure limits do not belong here. Start with relationships optional until provider readiness is certified; missing mandatory/stale/invalid evidence then fails closed. Correlation modifies context confidence only; initial divergence is warning/contradiction, not a final trade block.

## 7. Correlation methodology and safeguards

Use Pearson correlation on aligned **returns**, never price levels (common price trends can create spurious correlation). Receive completed canonical candles of one timeframe/session semantics, intersect timestamps deterministically, and do not silently discard missing observations. Exclude partial/current candles before returns. Require policy-minimum aligned prices and at least two returns; recommended initial minimum is 30 returns pending replay/provider validation.

Reject non-finite price/return, duplicate/out-of-order/misaligned timestamps, incompatible sessions, zero variance, non-finite coefficient, stale/future source, or insufficient sample. Implement population covariance / product of population standard deviations with the standard library, not NumPy. Rolling windows are explicit, trailing, and no-look-ahead.

Correlation is descriptive, unstable, and non-causal. Strong positive relationship plus matching directions confirms; the same relationship plus opposing directions diverges. Negative correlation is context, not automatically bearish. Do not score technical direction twice or treat BANKNIFTY and FINNIFTY as independent financial-sector confirmations; at first permit one configured pair contribution per primary. Divergence warns/contradicts initially; a future policy may block only after replay evidence.

## 8. Integration boundaries

P5-8 consumes the core identity registry and supplied P5-2/P5-3 quality-gated candles. A future adapter may compare supplied technical direction, but canonical code must not import technical evaluators or calculate indicators. It has no option-chain dependency except later consumers combining separate result IDs.

P5-8 owns evidence, aggregation, source timestamps, warnings, and contradictions. It does not own market regime, final decision, option selection, `TradeOpportunityV1` change, score/risk formulas, dashboard, paper/live execution, or capital reservation. Future four-market opportunity ranking is a separately versioned integration. P8 owns portfolio-state-aware correlated exposure and open-position enforcement.

## 9. Proposed implementation and test files

Future implementation: the five contracts and six package files in section 5; optional public-contract documentation under `docs/contracts/`. Provider adapters must live outside contracts/domain packages.

- `tests/test_cross_market_evidence_v1.py`: immutability, pair/identity/types/times/sources, bounds, serialization.
- `tests/test_market_breadth_evidence_v1.py`: arithmetic/coverage, unavailable vs neutral, heavyweight, stale/future/partial inputs.
- `tests/test_volatility_context_v1.py`: regimes, unavailable VIX, finite/timestamp checks, semantic serialization.
- `tests/test_broader_market_intelligence_policy_v1.py`: pair order, thresholds, weights, optional/mandatory restrictions.
- `tests/test_broader_market_correlation.py`: all identities; NIFTY/SENSEX and BANKNIFTY/FINNIFTY confirmation/divergence; positive/negative/weak, insufficient, zero variance, missing/misaligned/partial/stale/future observations.
- `tests/test_broader_market_breadth.py`: A/D, coverage, missing/incomplete breadth, heavyweight states, deterministic strength.
- `tests/test_broader_market_volatility.py`: VIX context and high-volatility warning/block policy.
- `tests/test_broader_market_intelligence_evaluator.py`: aggregation, contradictions, unearned unavailable weight, fail-closed required evidence, no random or execution side effects.
- `tests/test_broader_market_intelligence_isolation.py`: clean-process imports exclude pandas, NumPy, requests, yfinance, Streamlit, SmartAPI, broker/provider/execution/UI modules.
- `tests/test_broader_market_integration_contract.py`: future supplied-result compatibility without decision/opportunity changes.

## 10. Compatibility risks

Main risks: absent evidence becoming neutral, duplicate technical/VIX/regime scoring, accidental pandas/provider imports, unproven BSE feeds, plausible correlation from stale/misaligned candles, and context altering current trade/execution behavior. Mitigate through strict frozen contracts, source IDs/times, explicit optionality, clean-process isolation, replay fixtures, and no runtime integration before certification.

## 11. Ordered P5-8 plan

1. **P5-8B:** contracts and four-identity/serialization tests.
2. **P5-8C:** policy and pair registry/threshold tests.
3. **P5-8D:** pure standard-library correlation/alignment evaluator.
4. **P5-8E:** pure supplied-count breadth evaluator.
5. **P5-8F:** pure provider-normalized VIX evaluator.
6. **P5-8G:** aggregate evaluator with deterministic unavailable/blocker/contradiction behavior.
7. **P5-8H:** exports and isolated supplied integration seam; no decision/opportunity/execution wiring.
8. **P5-8I:** four-index replay, isolation, determinism, and side-effect tests.
9. **P5-8J:** compatibility/certification externally, proving legacy/current outputs unchanged. Provider readiness is a separate audit.

## 12. Explicit non-goals

P5-8A creates no Python engine, provider integration, network/cache/UI behavior, contract ranking, decision, opportunity, risk rule, portfolio reservation/open-position control, paper/live order, or test modification. It makes no causal claim and does not assert provider support without code evidence.

## 13. Open questions

1. Which approved provider supplies completed, timestamped SENSEX and all NSE index candles at common cadence?
2. Does it provide India VIX value/change/source timestamps, and what are session/update semantics?
3. Which licensed source supplies A/D counts, constituent universe/weights, and heavyweight contribution?
4. What authoritative breadth scope and suspended/unchanged-constituent treatment applies to each index?
5. How are NSE/BSE holidays, pre-open, auctions, and partial sessions aligned?
6. Which later P5-7 decision/ranking contract owns an additive broader-result link without changing `TradeOpportunityV1` semantics?
7. Should high VIX or strong divergence ever block, or remain context-only after replay evidence?

