# Task 2A — Analytical Engine Examination

## Executive finding

Task 2A is examination only: no production code was changed. The active
certified per-market analytical path is:

`CertifiedCycleSource` → `CertifiedLiveProviderReaders.read_data()` →
`CertifiedLiveAnalysisAuthority` / `LiveAnalysisPipeline` →
`CertifiedLiveOpportunityAuthority` / `LiveOptionDecisionPipeline`.

It correctly preserves a supplied NIFTY/NSE/NFO or SENSEX/BSE/BFO identity and
is PAPER-only. It is not a complete typed candidate-evidence pipeline: the
live analysis output is a mutable dictionary assembled from several legacy
engines, while the newer typed technical, option-chain, regime, external and
broader-market libraries are largely supplied-evidence-only and are not
composed into the certified opportunity result. Task 2B must implement only
the accepted authoritative seams below. Task 3 alone owns cross-market
comparison/ranking.

## Authoritative production path

| Stage | Current authority | Input/output | Identity, freshness and failure behavior |
| --- | --- | --- | --- |
| Market identity | `certified_live_provider_readers.market_spec_for()` | `(symbol, exchange)` → `CertifiedIndexMarketSpecV1` | Exact NIFTY/NSE/NFO or SENSEX/BSE/BFO only; unsupported tuple raises. |
| Quote/session/data | `CertifiedLiveProviderReaders.read_data()` and certified authorities | `PaperOrchestrationCycleInputV1` → `CertifiedLiveDataResultV1` | Validates identity/timestamp; mismatches raise/fail closed. |
| Candles/analysis | `LiveMultiTimeframeData` and `LiveAnalysisPipeline` | exchange/token → OHLCV DataFrames → dict | Empty 5m or invalid OHLCV raises; cache TTL is timeframe-specific but not typed provenance. |
| Opportunity/options | `LiveOptionDecisionPipeline` and `LiveOptionChainBuilder` | analysis dict + spot + option exchange → dict → `CertifiedLiveOpportunityResultV1` | NFO/BFO passed from market spec; safety gates return NO_TRADE/WAIT rather than broker execution. |

The active path is single-market configured evaluation. Running SENSEX replaces
NIFTY; Task 2B must not compare them or integrate the four-market ranker.

## Complete pillar matrix

Legend: **D/E/C** means affects direction / eligibility / confidence.
“Evidence” states output retention. NIFTY and SENSEX support are both `Y` only
when the authoritative path accepts the supplied identity; this is not a Task 3
claim that both are scheduled together.

| # | Pillar and status | Authority; input → output | NIFTY/SENSEX; NFO/BFO | Freshness; failure/fallback | D/E/C; evidence; tests | Duplicate or legacy |
| --- | --- | --- | --- | --- | --- |
| 1 | Quote/candles — READY_BUT_NOT_INTEGRATED | readers + `LiveMultiTimeframeData`; identity/token → DataFrames | Y/Y; underlying exchange correct | TTL 240s–21600s; empty candles raise; cache may reuse within TTL | D/Y/C; raw frames retained in dict; `test_live_multi_timeframe_data.py` | `market_data_manager.py`, root clients |
| 2 | Normalization — PARTIAL | `data_normalizer.normalize_angel_candles`; raw rows → DataFrame | Y/Y; no option routing | Coerce/drop invalid rows; no typed provenance | D/N/N; mutable frame; `test_data_normalizer.py` | adapters/legacy normalizers |
| 3 | Freshness — PARTIAL | session validation + option decision candle gate | Y/Y; Y/Y | Session/candle age gate; cache age not propagated as candidate evidence | Y/Y/C; session/reasons retained; candle tests | cache reuse is opaque |
| 4 | Data quality — READY_BUT_NOT_INTEGRATED | `data_quality/*`, option-chain quality contracts | Y/Y; option data Y/Y | Typed supplied timestamps/quality block; not joined to active dict | Y/Y/C; typed blockers; quality tests | live dict quality fields |
| 5 | Technical indicators — READY_BUT_NOT_INTEGRATED | `technical_intelligence/pipeline.py`; candle contracts → `TechnicalIntelligenceResultV1` | Y/Y; N/A | Insufficient data becomes unavailable evidence | Y/Y/Y; typed counts/blockers; canonical tests | `technical.py`, `technical_score.py` |
| 6 | Price action — PARTIAL | `PriceMarketStructureEngine`; OHLCV dict → dict | Y/Y; N/A | Invalid inputs depend on legacy engine | Y/Y/C; dict retained but not passed to strategy selector | `market_engine.py`, archive structure |
| 7 | Candlesticks — READY_BUT_NOT_INTEGRATED | typed patterns and `pattern_analyzer`; OHLCV → evidence/dict | Y/Y; N/A | Missing patterns neutral/no-action | Y/Y/C; dict/typed evidence; pattern tests | `analysis/candlestick_engine.py` |
| 8 | Chart patterns — PARTIAL | `chart_pattern_analyzer.analyse_chart_patterns`; DataFrame → dict | Y/Y; N/A | Legacy dict fallback/absence | Y/Y/C; active dict; chart tests | pattern engines overlap |
| 9 | Volume — READY_BUT_NOT_INTEGRATED | `analysis/volume_engine.py`, `volume_intelligence.py`, typed timeframe evidence | Y/Y; N/A | Missing/weak volume becomes neutral/warning | Y/Y/C; reasons retained; volume tests | multiple volume engines |
| 10 | Volatility — READY_BUT_NOT_INTEGRATED | typed volatility and regime contracts | Y/Y; N/A | Insufficient series is unavailable | Y/Y/C; typed strength/warnings; volatility tests | `market_regime_engine.py` VIX score |
| 11 | Market regime — READY_BUT_NOT_INTEGRATED | `market_regime/*`; typed contexts → canonical regime | Y/Y; N/A | Conflicts/blockers typed | Y/Y/Y; typed reasons; regime tests | `market_regime_engine.py` dict classifier |
| 12 | MTF alignment — READY_BUT_NOT_INTEGRATED | `multi_timeframe/*`; candle series → quality/snapshot | Y/Y; N/A | Missing anchor blocks/warns | Y/Y/Y; typed alignment; MTF tests | `multi_timeframe_analyzer.py` |
| 13 | Option-chain acquisition — READY_BUT_NOT_INTEGRATED | `LiveOptionChainBuilder`; underlying/option exchange → dict | Y/Y; NFO/BFO Y/Y | missing contracts/quotes fail closed in decision path | Y/Y/C; dict/audit; builder tests | `analysis/option_chain.py` is random and forbidden |
| 14 | OI — READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/oi_concentration.py` | Y/Y; NFO/BFO after provider adapter | typed quality controls missing data | Y/Y/C; typed metrics; OI tests | `options/oi_engine.py` |
| 15 | OI change — READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/oi_buildup.py` | Y/Y; NFO/BFO after adapter | neutral only for valid balanced data | Y/Y/C; typed metric; buildup tests | `options/oi_change_engine.py` |
| 16 | PCR — READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/pcr.py` | Y/Y; NFO/BFO after adapter | valid neutral is explicit | Y/Y/C; typed metric; PCR tests | root option helpers |
| 17 | Support/resistance — READY_BUT_NOT_INTEGRATED | option-chain SR + technical levels | Y/Y; NFO/BFO option path | missing levels warn/block per policy | Y/Y/C; typed metrics; SR tests | `analysis/support_resistance_engine.py` |
| 18 | Max pain — READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/max_pain.py` | Y/Y; NFO/BFO option path | explicit valid neutral possible | Y/Y/C; typed metric; max-pain tests | `options/max_pain_engine.py` |
| 19 | IV — READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/iv_skew.py` | Y/Y; NFO/BFO option path | thresholded neutral/warnings | Y/Y/C; typed metric; IV tests | raw live builder fields |
| 20 | Greeks — PARTIAL | `options/greeks_engine.py` / live option pipeline | Y/Y; NFO/BFO Y/Y | no typed canonical Greeks result in active candidate seam | Y/Y/C; dict/audit only; legacy tests | master decision dictionaries |
| 21 | Premium behavior — PARTIAL | `LiveOptionDecisionPipeline` / selected contracts | Y/Y; NFO/BFO Y/Y | price integrity gates; no canonical premium-behavior contract | Y/Y/C; audit dict; live option tests | legacy trade plan helpers |
| 22 | Liquidity/spread — PARTIAL | option-contract ranking evaluator | Y/Y; NFO/BFO when supplied | policy blocks/warns supplied evidence; active path integration unproven | N/Y/C; typed eligibility evidence; ranking tests | ad-hoc option selectors |
| 23 | Broader-market intelligence — READY_BUT_NOT_INTEGRATED | `broader_market_intelligence/*` | Y/Y; N/A | supplied missing components warn/block by policy | Y/Y/C; typed result; broader tests | `analysis/*` breadth/VIX/FII-DII |
| 24 | Sentiment — PARTIAL | external-context contracts; legacy news engines | Y/Y; N/A | supplied context can be unavailable; legacy may neutralize | Y/Y/C; typed context when supplied; external tests | `news.py`, `analysis/news_sentiment_engine.py` |
| 25 | External context — READY_BUT_NOT_INTEGRATED | `external_context/*` | Y/Y; N/A | conflicts and missing evidence are typed | Y/Y/C; provenance/results; context tests | legacy global/news paths |
| 26 | Contradictions — READY_BUT_NOT_INTEGRATED | technical/regime/option contracts | Y/Y; Y/Y | typed conflict/blocker/warning rules | Y/Y/Y; retained in contracts; canonical tests | dict strategy contradictions |
| 27 | Scoring — PARTIAL | typed ranking/scoring only for four-market candidates | Y/Y theoretically; no pair contract | policy-controlled; no active pair use | Y/Y/Y; typed candidate fields; ranking tests | `technical.py`, `technical_score.py`, `market_engine.py`, `scoring/*` |
| 28 | Confidence — PARTIAL | typed technical/regime outputs | Y/Y; N/A | unavailable evidence lowers/blocks typed result | Y/Y/Y; traceable there; canonical tests | multiple 0–100 dict confidences |
| 29 | Direction — PARTIAL | typed technical/regime plus live strategy dict | Y/Y; N/A | typed mixed/neutral; live uses strategy defaults | Y/Y/Y; typed/dict reasons; live tests | master decision/legacy engines |
| 30 | Eligibility — READY_BUT_NOT_INTEGRATED | option-contract ranking and P5/P6 policies | Y/Y; NFO/BFO after adapter | explicit blockers/no contract | N/Y/C; typed evidence; ranking tests | legacy selectors |
| 31 | Evidence provenance — PARTIAL | P5 contracts and provider readers | Y/Y; Y/Y | typed sources preserve IDs/timestamps; live dict loses a unified graph | Y/Y/Y; partial audit metadata; provenance tests | mutable nested dictionaries |
| 32 | Failure/fallback — PARTIAL | certified authorities/contracts | Y/Y; Y/Y | identity mismatch raises; session/quality return fail-closed no-trade; legacy paths silently neutralize | Y/Y/C; partial audit; resilience tests | broad legacy exception handlers |

## NIFTY and SENSEX paths

`market_spec_for("NIFTY", "NSE")` binds the NIFTY spot token and NFO;
`market_spec_for("SENSEX", "BSE")` binds the SENSEX spot token and BFO.
`CertifiedLiveProviderReaders` passes the same supplied underlying exchange and
token to candles and the matched option exchange to option-chain building.
Certified authorities reject symbol/exchange identity mismatches. This is the
only current authoritative routing statement; Task 2B must retain it and Task
3 must supply the future parallel/sequential pair coordinator.

## Duplicate and legacy paths

- `services/analysis/option_chain.py` generates random PCR/OI/levels: unsafe,
  legacy only, never import into certified path.
- `services/decision/master_decision_engine.py` imports `archive/*`, catches
  broad exceptions, and manufactures neutral MTF fallback dictionaries.
- `services/technical.py`, `technical_score.py`, `market_engine.py`,
  `market_regime_engine.py`, `services/scoring/*`, and `services/analysis/*`
  use overlapping mutable-dictionary scores, directions and confidence scales.
- `services/market_ranking_engine.py` and four-market ranking are not eligible
  Task 2 authorities; Task 3 owns a new exact two-market ranker.
- `services/options/*` and root option helpers may be useful adapters only when
  their input provenance and NFO/BFO routing are made explicit.
- `services/market_regime_indicators.py` does not exist; do not create it as a
  substitute for the accepted `market_regime/*` contract path.

## Unsafe fallbacks and high-risk findings

1. Random output exists in `services/analysis/option_chain.py`.
2. Default UUID factories occur in option-chain aggregation and option-contract
   ranking; deterministic certification must inject IDs.
3. `LiveMultiTimeframeData` defaults to `datetime.now()`, cache-enabled reads,
   and real `sleep`; deterministic callers must inject data and time.
4. `LiveOptionDecisionPipeline` retains a completed-candle broker fallback and
   catches broad `Exception` around audit persistence. Task 2B must make its
   active analytical dependency boundary explicit, not silently substitute
   unproven data.
5. `technical_score.py` returns neutral zero scores for missing/empty inputs;
   `market_engine.py`/`market_regime_engine.py` similarly accept empty mapping
   pathways. These are legacy compatibility behavior, not certified evidence.
6. `LiveAnalysisPipeline` calculates market structure but does not pass it to
   `select_strategy`; its mutable dictionary has no unified typed provenance.
7. `LiveOptionDecisionPipeline` defaults missing strategy decision/direction to
   `NO_TRADE`/`NEUTRAL`, which is fail-safe but must be represented as an
   explicit unavailable/blocked reason in the future candidate.

## Missing integration seams and proposed immutable per-market candidate

Task 2B needs the supplied-evidence-only immutable `MarketAnalysisCandidateV1`
contract defined below, for one identity only. It must contain:

- exact `(underlying_symbol, exchange, option_exchange, symboltoken)`;
- observation/request/received timestamps plus freshness and data-quality
  results;
- exact typed technical, multi-timeframe, regime, option-chain, option-contract
  eligibility, broader-market and external-context results where available;
- direction, confidence, eligibility and status derived from named evidence;
- blockers, warnings, contradictions, evidence references/provenance, and an
  explicit `NO_TRADE`/unavailable outcome;
- `execution_mode="PAPER"` and `live_execution_eligible=False`.

It must not fetch providers, generate a clock/ID unless injected, rank markets,
select the cross-market winner, build P6, mutate P7/P8, or call a broker.

## Exact Task 2B slices

1. Define and test the per-market typed candidate/evidence boundary with no
   provider, broker, dashboard, P6, P7, P8, or ranking import.
2. Add explicit adapters from the currently active live-analysis/option result
   only after they expose provenance, quality/freshness and exact identity.
3. Select canonical technical/MTF/regime/option-chain/external results and
   reject silent neutral, random, synthetic, stale or untyped fallback values.
4. Add deterministic injected-clock/ID seams at any accepted adapter boundary.
5. Preserve the existing NIFTY/NSE/NFO and SENSEX/BSE/BFO route; do not schedule
   or compare markets until Task 3.

## Likely files to change and tests to add

Likely Task 2B changes: `services/contracts/` (new per-market contract),
`services/paper_orchestration/certified_live_provider_readers.py`,
`certified_live_read_authorities.py`, `services/live_analysis_pipeline.py`,
`services/live_option_decision_pipeline.py`, and narrowly scoped adapters.
Likely tests: new contract/isolation tests; deterministic NIFTY and SENSEX
candidate fixtures; routing mismatch, stale cache, missing/empty candles,
missing/malformed option chain, random/synthetic fallback rejection, evidence
traceability, direction/confidence/eligibility contradiction, and injected ID/
clock tests. Preserve existing `test_live_analysis_pipeline.py`,
`test_live_option_decision_pipeline.py`, `test_live_option_chain_builder.py`,
`test_canonical_technical_intelligence_pipeline.py`,
`test_option_chain_intelligence_pipeline.py`, `test_*market_regime*`,
`test_*multi_timeframe*`, `test_*external_context*`, and
`test_two_market_runtime_readiness.py`.

## Compatibility risks and Task 2 completion gates

Risks: callers expect pandas/dictionary outputs; legacy code has conflicting
score scales and neutral defaults; live provider cache/time behavior is not
fully injectable; four-market contracts must remain unused by certified pair
work. Compatibility adapters must be explicit and read-only.

Task 2 is complete only when the Task 2A matrix is accepted; one immutable,
deterministic, explainable per-market candidate is tested for both identities;
all accepted evidence is typed/provenanced/freshness-qualified; unsafe legacy
fallbacks are excluded; no broker submission or live eligibility is introduced;
and Task 3 receives no ranking implementation from Task 2B.

## Implementation-ready authority matrix

This matrix supersedes the shorthand matrix above. `Canon` and `Runtime` name
the library authority and present certified behavior separately. `In→Out` gives
exact types; `F/Fb` gives freshness, failure and fallback; `D/E/C` gives
direction, eligibility and confidence; `Ev/Test` gives provenance and focused
tests. `Y/Y` means NIFTY/SENSEX when supplied; `NFO/BFO` means routing relevance.

| # | Canon (file :: function/type) | Contract | Runtime :: caller | In→Out; N/S; NFO/BFO | F/Fb; D/E/C; Ev/Test | Legacy; class |
|---|---|---|---|---|---|---|
|1|`services/data_quality/quote_quality.py::evaluate_market_quote_quality`|`contracts/market_data_quality_result_v1.py::MarketDataQualityResultV1`|`certified_live_provider_readers.py::read_data` :: `CertifiedLiveDataAuthority.__call__`|`PaperOrchestrationCycleInputV1→dict`;Y/Y;N/A|timestamp validation/raise;Y/Y/C; reader metadata/`test_quote_data_quality.py`|root market clients; READY_BUT_NOT_INTEGRATED|
|2|`services/market/live_multi_timeframe_data.py::LiveMultiTimeframeData.fetch_all`|MISSING|same :: `CertifiedLiveProviderReaders.read_analysis`|`str,str→dict[str,DataFrame]`;Y/Y;N/A|TTL/empty raises/cache fallback;Y/Y/C; dict/`test_live_multi_timeframe_data.py`|market managers; PARTIAL|
|3|`services/data_normalizer.py::normalize_angel_candles`|MISSING|`LiveAnalysisPipeline._normalize_timeframes` :: `LiveAnalysisPipeline.analyse`|rows→`DataFrame`;Y/Y;N/A|drop invalid/no provenance;Y/N/N; frame/`test_data_normalizer.py`|adapters; PARTIAL|
|4|`data_quality/freshness.py::evaluate_candle_freshness`|`MarketDataQualityResultV1`|`LiveOptionDecisionPipeline._analyse_core` :: `analyse`|candle→quality;Y/Y;N/A|age blocks/no-trade;Y/Y/C; session dict/`test_candle_data_quality.py`|TTL cache; READY_BUT_NOT_INTEGRATED|
|5|`technical_intelligence/pipeline.py::build_canonical_technical_intelligence`|`TechnicalIntelligenceResultV1`|`live_analysis_pipeline.py::LiveAnalysisPipeline.analyse` :: reader `read_analysis`|series→result / dict;Y/Y;N/A|typed unavailable vs dict;Y/Y/Y; result/dict/`test_canonical_technical_intelligence_pipeline.py`|`technical.py`; READY_BUT_NOT_INTEGRATED|
|6|MISSING|MISSING|`analysis/price_market_structure_engine.py::PriceMarketStructureEngine.analyze` :: `LiveAnalysisPipeline.analyse`|dict→dict;Y/Y;N/A|legacy behavior;Y/Y/C; dict/`test_live_analysis_pipeline.py`|archive structure; PARTIAL|
|7|MISSING|MISSING|`pattern_analyzer.py::analyse_patterns` :: `LiveAnalysisPipeline.analyse`|DataFrame→dict;Y/Y;N/A|neutral absence;Y/Y/C; dict/`test_pattern_analyzer.py`|`analysis/candlestick_engine.py`; PARTIAL|
|8|MISSING|MISSING|`chart_pattern_analyzer.py::analyse_chart_patterns` :: `LiveAnalysisPipeline.analyse`|DataFrame→dict;Y/Y;N/A|legacy dict;Y/Y/C; dict/`test_chart_pattern_analyzer.py`|pattern analyzers; PARTIAL|
|9|MISSING|MISSING|`volume_intelligence.py::analyse_volume_intelligence` :: `LiveAnalysisPipeline.analyse`|DataFrame→dict;Y/Y;N/A|neutral weak volume;Y/Y/C; dict/`test_volume_intelligence.py`|`analysis/volume_engine.py`; PARTIAL|
|10|MISSING|`contracts/volatility_context_v1.py::VolatilityContextV1`|`market_regime_analyzer.py::analyse_market_regime` :: pipeline|dict→dict;Y/Y;N/A|dict neutral;Y/Y/C; dict/`test_volatility_context_evaluator.py`|`market_regime_engine.py`; PARTIAL|
|11|`market_regime/service.py::evaluate_market_regime`|`CanonicalMarketRegimeResultV1`|`market_regime_analyzer.py::analyse_market_regime` :: pipeline|typed input→result / dict;Y/Y;N/A|typed blockers;Y/Y/Y; result/dict/`test_market_regime_policy_v1.py`|`market_regime_engine.py`; READY_BUT_NOT_INTEGRATED|
|12|`multi_timeframe/pipeline.py::build_canonical_multi_timeframe_snapshot`|`MultiTimeframeSnapshotV1`|`multi_timeframe_analyzer.py::analyse_multi_timeframe` :: pipeline|series→snapshot / dict;Y/Y;N/A|missing anchor warns;Y/Y/Y; result/dict/`test_canonical_multi_timeframe_pipeline.py`|live MTF engine; READY_BUT_NOT_INTEGRATED|
|13|MISSING|MISSING|`live_option_chain_builder.py::LiveOptionChainBuilder.build_chain` :: `LiveOptionDecisionPipeline._analyse_core`|identity,spot→dict;Y/Y;Y/Y|missing quotes no-trade;Y/Y/C; audit dict/`test_live_option_chain_builder.py`|`analysis/option_chain.py`; PARTIAL|
|14|`option_chain_intelligence/intelligence_pipeline.py::build_canonical_option_chain_intelligence`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→result;Y/Y;Y/Y|typed quality;Y/Y/C; result/`test_option_chain_intelligence_pipeline.py`|`options/oi_engine.py`; READY_BUT_NOT_INTEGRATED|
|15|`option_chain_intelligence/oi_buildup.py::evaluate_oi_buildup`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→metric;Y/Y;Y/Y|explicit neutral;Y/Y/C; result/`test_option_chain_oi_buildup.py`|`options/oi_change_engine.py`; READY_BUT_NOT_INTEGRATED|
|16|`option_chain_intelligence/pcr.py::evaluate_pcr`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→metric;Y/Y;Y/Y|explicit neutral;Y/Y/C; result/`test_option_chain_pcr.py`|root PCR; READY_BUT_NOT_INTEGRATED|
|17|`option_chain_intelligence/support_resistance.py::evaluate_support_resistance`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→metric;Y/Y;Y/Y|quality blockers;Y/Y/C; result/`test_option_chain_support_resistance.py`|`analysis/support_resistance_engine.py`; READY_BUT_NOT_INTEGRATED|
|18|`option_chain_intelligence/max_pain.py::evaluate_max_pain`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→metric;Y/Y;Y/Y|valid neutral;Y/Y/C; result/`test_option_chain_max_pain.py`|`options/max_pain_engine.py`; READY_BUT_NOT_INTEGRATED|
|19|`option_chain_intelligence/iv_skew.py::evaluate_iv_skew`|`OptionChainIntelligenceResultV1`|NONE :: NONE|snapshot→metric;Y/Y;Y/Y|threshold neutral;Y/Y/C; result/`test_option_chain_iv_skew.py`|raw fields; READY_BUT_NOT_INTEGRATED|
|20|MISSING|MISSING|`options/greeks_engine.py` :: live option pipeline|dict→dict;Y/Y;Y/Y|untyped fallback;Y/Y/C; dict/`test_option_agent.py`|master decision; PARTIAL|
|21|MISSING|MISSING|`LiveOptionDecisionPipeline._analyse_core` :: `analyse`|dict→dict;Y/Y;Y/Y|price gate/no-trade;Y/Y/C; audit/`test_live_option_decision_pipeline.py`|legacy plans; PARTIAL|
|22|`option_contract_ranking/ranking_pipeline.py::build_canonical_option_contract_ranking`|`OptionContractRankingResultV1`|NONE :: NONE|universe→result;Y/Y;Y/Y|policy blockers;N/Y/C; result/`test_option_contract_ranking_pipeline.py`|selectors; READY_BUT_NOT_INTEGRATED|
|23|`broader_market_intelligence/integration.py::build_broader_market_intelligence`|`BroaderMarketIntelligenceResultV1`|NONE :: NONE|series→result;Y/Y;N/A|typed missing warnings;Y/Y/C; result/`test_broader_market_intelligence_integration.py`|analysis breadth; READY_BUT_NOT_INTEGRATED|
|24|MISSING|MISSING|NONE :: NONE|none;Y/Y;N/A|neutral legacy;Y/Y/C; none/`test_external_context_integration.py`|news engines; MISSING|
|25|`external_context/integration.py::evaluate_external_context_pipeline`|`ExternalMarketContextResultV1`|NONE :: NONE|observations→result;Y/Y;N/A|typed conflicts;Y/Y/C; result/`test_external_context_integration.py`|news/global; READY_BUT_NOT_INTEGRATED|
|26|`market_regime/service.py::evaluate_market_regime`|`CanonicalMarketRegimeResultV1`|`regime_aware_evidence.py::evaluate_regime_aware_evidence` :: pipeline|typed/dicts→dict;Y/Y;N/A|blockers/warnings;Y/Y/Y; dict/`test_p5_10h1_market_regime_aggregation.py`|strategy dict; PARTIAL|
|27|MISSING|MISSING|`strategy_selector.py::select_strategy` :: pipeline|dicts→dict;Y/Y;N/A|score scales conflict;Y/Y/Y; dict/`test_live_analysis_pipeline.py`|technical/market/scoring engines; PARTIAL|
|28|`technical_intelligence/aggregation.py::aggregate_technical_intelligence`|`TechnicalIntelligenceResultV1`|`strategy_selector.py::select_strategy` :: pipeline|evidence→result/dict;Y/Y;N/A|typed traceable, live not;Y/Y/Y; result/dict/`test_technical_intelligence_aggregation.py`|0-100 dict confidence; PARTIAL|
|29|`technical_intelligence/aggregation.py::aggregate_technical_intelligence`|`TechnicalIntelligenceResultV1`|`strategy_selector.py::select_strategy` :: pipeline|evidence→bias/dict;Y/Y;N/A|mixed/neutral;Y/Y/Y; reasons/`test_technical_intelligence_result_v1.py`|master decision; PARTIAL|
|30|`option_contract_ranking/evaluator.py::evaluate_option_contract`|`OptionContractRankingResultV1`|`LiveOptionDecisionPipeline._analyse_core` :: `analyse`|candidate→result/dict;Y/Y;Y/Y|no-contract;N/Y/C; result/audit/`test_option_contract_ranking_evaluator.py`|legacy selector; PARTIAL|
|31|MISSING|MISSING|certified readers :: authorities|dicts→dicts;Y/Y;Y/Y|partial metadata only;Y/Y/Y; audit/`test_market_data_provenance_v1.py`|mutable dictionaries; PARTIAL|
|32|MISSING|MISSING|certified authorities :: complete cycle|contracts/dicts→results;Y/Y;Y/Y|raise/no-trade;Y/Y/Y; journal/`test_weekend_paper_resilience.py`|broad legacy handlers; PARTIAL|

## Frozen contract: `MarketAnalysisCandidateV1`

`MarketAnalysisCandidateV1` is the single Task 2B per-market immutable
candidate name. It is not a ranker, selector, P6/P7/P8 input, provider, or
broker client.

| Field | Type | Required | Source evidence | Unavailable/failure representation |
|---|---|---|---|---|
|`candidate_id`,`observation_id`|`str`|Y|injected ID/cycle observation|construction rejects blank|
|`underlying_symbol`,`exchange`,`option_exchange`,`symboltoken`|`str`|Y|market spec|reject not NIFTY/NSE/NFO or SENSEX/BSE/BFO|
|`requested_at`,`market_timestamp`,`received_at`|aware `datetime`|Y|cycle/quote|reject invalid ordering|
|`freshness`,`data_quality`,`session`|`MarketDataQualityResultV1`,`MarketDataQualityResultV1`,`MarketSessionValidationV1`|Y|P5/session|typed BLOCKED/UNAVAILABLE; never neutral|
|`technical`,`multi_timeframe`,`regime`|`TechnicalIntelligenceResultV1`,`MultiTimeframeSnapshotV1`,`CanonicalMarketRegimeResultV1`|Y|canonical pipelines|typed unavailable/blockers|
|`price_action`,`candlestick`,`chart_pattern`,`volume`,`volatility`|immutable `Mapping[str, object]`|Y|approved adapters|`status="UNAVAILABLE"` plus blocker|
|`option_chain`,`oi`,`oi_change`,`pcr`,`support_resistance`,`max_pain`,`iv`|`OptionChainIntelligenceResultV1`|Y|canonical option intelligence|typed unavailable metric/blocker|
|`greeks`,`premium_behavior`,`liquidity_spread`|immutable `Mapping[str, object]`|Y|approved adapter/ranking evidence|`status="UNAVAILABLE"` plus blocker|
|`broader_market`,`external_context`|`BroaderMarketIntelligenceResultV1`,`ExternalMarketContextResultV1`|optional|canonical supplied context|`None` plus warning/blocker|
|`contradictions`,`warnings`,`blockers`,`reasons`,`invalidation_conditions`|`tuple[str,...]`|Y|aggregator|explicit codes; no silent neutral|
|`direction`|`Literal["BULLISH","BEARISH","NEUTRAL","UNAVAILABLE","CONFLICTING"]`|Y|named evidence|UNAVAILABLE/CONFLICTING|
|`eligibility`|`Literal["ELIGIBLE","INELIGIBLE","UNAVAILABLE","CONFLICTING"]`|Y|policy aggregation|non-eligible state|
|`confidence`,`score`|`float`|Y|traceable aggregation|`0.0` only with explicit blocker|
|`evidence_references`,`provenance`|immutable `Mapping[str,str]`|Y|result IDs/timestamps/provider|reject missing required references|
|`execution_mode`,`live_execution_eligible`,`broker_order_submission`|`Literal["PAPER"]`,`Literal[False]`,`Literal[False]`|Y|safety policy|reject any other value|

## Exact Task 2B ordered slices

1. **Contract/isolation.** Change `services/contracts/market_analysis_candidate_v1.py` and exports only; add `tests/test_market_analysis_candidate_v1.py` and isolation test. Entry: Task 2A acceptance. Gate: immutable construction, PAPER flags, exact identity, explicit unavailable states. Risk: contract import cycles.
2. **Canonical supplied-evidence composer.** Change `services/analysis/market_analysis_candidate_composer.py` only after contract; add composer deterministic fixtures/tests. Entry: Slice 1. Gate: no fetch, current time, UUID, ranking or selection. Risk: conflating adapter data with evidence authority.
3. **Technical/MTF/regime adapters.** Change only approved adapters beside `technical_intelligence/pipeline.py`, `multi_timeframe/pipeline.py`, `market_regime/service.py`; add per-market provenance/freshness/contradiction tests. Entry: Slice 2. Gate: NIFTY and SENSEX independent candidate outputs. Risk: legacy dict score scale.
4. **Option/external adapters.** Change approved adapters beside option-chain, option-ranking, broader and external pipelines; add NFO/BFO, missing Greeks/premium/liquidity, malformed chain and unavailable context tests. Entry: Slice 3. Gate: no random/synthetic/silent-neutral evidence. Risk: live builder remains untyped.
5. **Certified read seam.** Change `certified_live_provider_readers.py` and `certified_live_read_authorities.py` only to attach one candidate per existing child cycle; add no-network injected clock/ID tests. Entry: Slice 4. Gate: existing single-market runtime behavior preserved; no Task 3 comparison. Risk: mutable live dictionaries.

## Task 2B prohibited imports and dependencies

`MarketAnalysisCandidateV1` and its composer must not import broker submission
or order clients, dashboard modules, P6, P7, P8, four-market ranking,
`services/market_ranking_engine.py`, `services/analysis/option_chain.py`, or
archive decision engines. They must not schedule, compare, rank, select, fetch
providers, submit orders, or set live eligibility.
