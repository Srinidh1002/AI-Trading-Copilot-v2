# P5-0 data and intelligence audit

## 1. Executive summary

**Decision: READY_WITH_BLOCKERS.** P4 is a strong, isolated paper-entry
boundary, but the upstream intelligence layer is not yet a trustworthy
four-index production decision source. The strongest components are immutable
P3/P4 contracts, canonical market identity, Angel request controls, replay
fixtures, and explicit failure boundaries. Highest risks are duplicated live
data paths, no canonical freshness/quality result, persistent cache behavior,
legacy NIFTY defaults, and ungoverned/partial option and intelligence inputs.
This is audit-only; P5-1 must establish the canonical universe before behavior
is migrated.

## 2. Repository inventory

| Path | Responsibility/API | Provider/input | Markets/timeframes | Cache/failure | Class |
|---|---|---|---|---|---|
| `services/core/market_identity.py` | canonical identity normalization | none | four pairs | fail closed | CANONICAL |
| `services/contracts/market_snapshot_v1.py` | immutable OHLCV snapshot | adapters | identity present | validation/blockers | CANONICAL |
| `services/market_data.py` | `get_stock_data`, `get_chart_data` | yfinance | arbitrary tickers; period/interval | no cache; wraps errors | COMPATIBILITY |
| `services/market/live_multi_timeframe_data.py` | Angel candle fetch | injected/default Angel client | 5m/15m/1h/1d | file cache; empty raises | COMPATIBILITY |
| `services/historical_data_cache.py` | JSON candle cache | filesystem | exchange/token/timeframe | TTL caller supplied | LEGACY |
| `services/broker/market_data_control.py` | rate/cached request control | Angel | endpoint neutral | locked memory TTL | CANONICAL-ADJACENT |
| `services/live_option_chain_builder.py`, `services/option_chain_live.py` | chain acquisition | NSE client | defaults NIFTY | module client/global | LEGACY |
| `services/option_ai.py`, `services/options/*_engine.py` | chain scores | mapping input | no canonical universe | unavailable→neutral-ish scores | COMPATIBILITY |
| `services/indicator_engine.py`, `services/indicators/*.py` | technical indicators | DataFrames | caller-defined | varied validation | LEGACY |
| `services/market_regime_analyzer.py` | regime classification | enriched DataFrame | caller-defined | raises missing columns | COMPATIBILITY |
| `services/analysis/*`, `services/decision/*` | analysis/decision engines | mixed mappings | mostly legacy NIFTY paths | varied defaults | LEGACY/UNKNOWN |

Tests exist for Angel resilience/control, completed-candle integrity, live
multi-timeframe data, market snapshots, canonical analysis/decision pipelines,
option contract selection, and replay fixtures. Many legacy files have only
mock-oriented or no direct coverage.

## 3. Market-data provider matrix

| Provider/client | File(s) | Capability | Auth/network | Cache/retry/failure | Risk |
|---|---|---|---|---|---|
| yfinance | `services/market_data.py` | quote + OHLCV | direct network, no injected client | no timeout/retry/cache; exceptions become `ValueError` | HIGH |
| Angel/SmartAPI | `broker/angel_client.py`, `market/live_multi_timeframe_data.py` | historical candles, broker data | credentials/session; network | rate controller, injected client, memory/file cache | MEDIUM |
| NSE client | `nse_client.py`, `option_chain_live.py` | option chain | direct network, lazy global client | no formal freshness/retry contract | HIGH |
| Dhan/other broker paths | broker/legacy modules | mixed | credentials/network | integration-specific | UNKNOWN |

Direct calls bypass provider-neutral abstractions in yfinance/NSE modules.
Provider payloads remain common mapping inputs; duplicate client and instrument
registries exist under `services/broker`, `services/market`, and options.

## 4. Canonical data-contract matrix

`MarketSnapshotV1`, `AnalysisResultV1`, `FinalDecisionV1`, session, option,
trade-plan, risk, and P4 contracts are frozen/serialized canonical boundaries.
`MarketSnapshotV1` supplies OHLCV/identity validation; it does not provide one
universal quote age, provider provenance, quality score, or canonical timeframe
model. Legacy DataFrames/dicts compete with contracts across data, indicators,
options, and regime engines. No canonical quote, option-chain intelligence,
sentiment, or regime result contract exists.

## 5. Four-index support matrix

| Capability | NIFTY/NSE | BANKNIFTY/NSE | FINNIFTY/NSE | SENSEX/BSE | Evidence |
|---|---|---|---|---|---|
| Identity/session/P3-P4 contracts | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | `market_identity.py`, contracts |
| Angel candles by token | PARTIAL | PARTIAL | PARTIAL | PARTIAL | live MTF accepts exchange/token |
| Quote/yfinance | PARTIAL | PARTIAL | PARTIAL | PARTIAL | arbitrary symbol, no registry |
| Technical/MTF | PARTIAL | PARTIAL | PARTIAL | PARTIAL | DataFrame-only engines |
| Option chain | PARTIAL | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | NSE default NIFTY paths |
| Sentiment/breadth/global/events | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | no canonical sources |
| Regime/decision/ranking | PARTIAL | PARTIAL | PARTIAL | PARTIAL | mapping/DataFrame engines; no ranking |
| Dashboard | PARTIAL | PARTIAL | PARTIAL | PARTIAL | legacy dashboard paths |

## 6. Freshness and quality audit

Angel cache TTLs are 240s/600s/2700s/21600s by timeframe. `HistoricalDataCache`
rejects expired/future cache timestamps and empty data, but persists JSON and
does not validate candle chronology/content. `MarketDataRequestController` has
locked in-memory TTL/rate limiting. No canonical quote timestamp/age policy,
provider disagreement rule, quality score, duplicate/out-of-order candle rule,
or cross-provider stale fallback contract exists. Time handling mixes naive
`datetime.now()` in live MTF with contract-aware timestamps elsewhere.

## 7. Cache audit

`HistoricalDataCache` key is `EXCHANGE:symboltoken:timeframe`; it includes
exchange/timeframe but no provider identity, is persistent, not thread-safe,
and has no explicit invalidation beyond TTL. `MarketDataRequestController` is
thread-safe, in-memory, keyed by caller-controlled key, and TTLs responses.
Neither should be promoted before P5-2 freshness/provenance rules.

## 8. Multi-timeframe audit

Angel direct intervals are 5m, 15m, 1h, 1d, with fixed lookbacks 3/10/45/365
days. There is no canonical resampling, incomplete-bar policy, IST/UTC
normalization, synchronized snapshot, warm-up requirement, or one canonical
multi-timeframe contract. `multi_timeframe_*` modules duplicate behavior.

## 9. Technical intelligence audit

Implementations include RSI, EMA, MACD, ADX, ATR, VWAP and indicator engines
under `services/indicators`, plus trend, volume, patterns, support/resistance,
and market-strength engines. `market_regime_analyzer.py` uses EMA20/EMA50,
ADX>=25, ATR percent thresholds, and Bollinger width<=2; confidence begins at
50 with hardcoded adjustments. Inputs are enriched DataFrames, not a canonical
quality-gated contract. Formula duplication, insufficient-history behavior,
NaN handling, weighting, and look-ahead controls need P5-3/P5-4 certification.

## 10. Option-chain intelligence audit

NSE (`nse_client.py`, `option_chain_live.py`) and Angel options clients coexist.
`option_ai.py` weights PCR/OI/writing/max pain/premium/IV/Greeks/liquidity and
degrades unavailable fields to zero evidence. PCR/max pain/support/resistance
come from mapping inputs; expiry discovery, stale-chain rules, full bid/ask,
and four-market routing are not canonical. NIFTY defaults make BANKNIFTY,
FINNIFTY, and SENSEX unsupported/untested for a trustworthy chain path.

## 11–13. Broader, global, sentiment, and regime audit

Breadth, VIX, FII/DII, news, global, correlation, and event modules exist
under `services/analysis`, `services/news.py`, and research modules, but no
provider-neutral live contracts, freshness rules, or four-index evidence matrix
exists. Regime is deterministic per supplied DataFrame but is not canonical,
quality-gated, or four-index certified.

## 14. Decision, confidence, and ranking audit

Legacy flows include `live_analysis_pipeline.py`, `live_option_decision_pipeline.py`,
analysis engines, master/decision engines, and dashboard mappings. Scores and
confidence are weighted mapping outputs, often with fallback values. Markets
are not independently normalized and ranked by one canonical four-market
opportunity contract. Therefore downstream P3/P4 should receive only existing
canonical/replay-certified evidence, not legacy live intelligence as trusted
P5 evidence.

## 15. Random/fabricated/placeholder/fallback register

| File | Behavior | Reachability/impact | P5 phase |
|---|---|---|---|
| `services/market_data.py` | yfinance arbitrary symbol compatibility | live quote/history, no provenance | P5-2 |
| `services/option_chain_live.py` | default `NIFTY`, global lazy client | option chain identity gap | P5-1/P5-5 |
| `services/option_ai.py` | unavailable chain fields become zero evidence | score/confidence degradation | P5-5 |
| `services/market_regime_analyzer.py` | fixed thresholds/confidence baseline | regime confidence | P5-8 |
| `historical_data_cache.py` | persistent JSON cache | stale/provenance boundary | P5-2 |
| legacy analysis/decision modules | mapping/default scores | decision trust | P5-3–P5-9 |

No P5-0 runtime use of random data was introduced. Search found fixtures/mocks
under tests; all runtime synthetic/default behavior must be classified before
P5 migration.

## 16–17. DI/isolation and test coverage

Angel MTF accepts client/cache injection but constructs defaults and reads an
environment toggle. Historical cache accepts path/time injection. yfinance and
NSE paths use direct/lazy globals. Existing test seams are strongest for Angel
control/cache and P3/P4 contracts; gaps cover provider payload normalization,
fresh/stale/future quotes, malformed chains, four-index chain data, broader
inputs, correlation, events, and canonical ranking.

## 18. Risk register

| Level | Issue/files | Failure/trading impact | P5 |
|---|---|---|---|
| CRITICAL | no canonical quality/freshness/provenance contract | stale/mixed evidence can influence intelligence | P5-2 |
| CRITICAL | no canonical four-market option-chain path | non-NIFTY opportunity decisions unsupported | P5-1/P5-5 |
| HIGH | duplicate providers/contracts/MTF engines | inconsistent calculations and identity leakage | P5-1/P5-3 |
| HIGH | legacy defaults and mapping fallbacks | false confidence/silent degraded decisions | P5-4–P5-9 |
| MEDIUM | persistent JSON cache | process/persistence/provenance incompatibility | P5-2 |
| MEDIUM | no canonical ranking | markets cannot be compared fairly | P5-9 |

## 19. Canonical target architecture

P5 should add, in order: registry-backed provider-neutral quote/candle and
quality contracts; freshness policy; canonical timeframe/multi-timeframe
snapshot; technical, option-chain, broader-market, global/event, and regime
results; four-market opportunity/ranking contracts; orchestration; and replay
observability boundaries. P3/P4 remain consumers of approved canonical
evidence and retain their current execution semantics.

## 20–21. Exact migration plan and order

| Phase | Objective and bounded scope |
|---|---|
| P5-1 | Canonical four-market universe; create registry adapters/contracts; retain legacy providers. |
| P5-2 | Quote/candle quality, freshness, provenance; isolate/deprecate JSON cache paths. |
| P5-3 | Canonical timeframe and multi-timeframe snapshot; do not migrate dashboards. |
| P5-4 | Quality-gated technical pillar and tests. |
| P5-5 | Provider-neutral option-chain intelligence and four-market routing. |
| P5-6 | Broader market/correlation result. |
| P5-7 | Global, institutional, sentiment, event result. |
| P5-8 | Deterministic regime result. |
| P5-9 | Opportunity ranking result. |
| P5-10 | Replay, regression, and certification. |

P5-1 is next. Do not migrate provider calls, Streamlit/dashboard behavior,
execution boundaries, or formulas before P5-2/P5-3 contracts are certified.
Use adapters and shadow comparisons for compatibility.

## 22. Final audit decision

**READY_WITH_BLOCKERS.** Blockers: canonical quality/freshness/provenance,
canonical four-market option-chain support, and unified MTF/ranking contracts.

## Certification evidence

- Audit invariants: `35 passed in 0.65s`.
- Identity regression: `178 passed in 0.86s`.
- P4 import/boundary regression: `138 passed in 0.75s`.
- Canonical intelligence regression command: `venv\Scripts\python.exe -m
  pytest` over the discovered analysis, market-data, multi-timeframe,
  option-chain/contract, regime, and decision tests; `386 passed, 2 warnings
  in 2.71s`.
- Import: `(('NIFTY', 'NSE'), ('BANKNIFTY', 'NSE'), ('FINNIFTY', 'NSE'),
  ('SENSEX', 'BSE'))` and `P5-0 imports passed`.
- Full repository: `6044 passed, 2 warnings in 16.38s`.

The only warnings are the pre-existing SmartAPI TLS deprecations. P5-0 changed
only this audit, the P5 roadmap, changelog, and audit-invariant test; no runtime
file was changed by P5-0. The worktree already contained unrelated modified and
untracked runtime files before the audit; none were reverted or incorporated.
