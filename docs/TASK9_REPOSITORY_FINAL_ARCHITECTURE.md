# Task 9 repository architecture

Audit date: 2026-08-10. Scope is Indian F&O NIFTY/SENSEX, PAPER-only Task 9.

## Active Task 9 path

`task9_live_paper_certification_launcher` performs the PAPER safety and ACTIVE
external-blocker gates, creates/loads the run manifest, then calls the Task 8
factory. Task 8 gets canonical two-market FULL quotes through the shared Angel
certification client, creates two cycle inputs, and invokes the authoritative
two-market parent cycle. Each child captures candles through
`LiveMultiTimeframeData`, options through `LiveOptionDecisionPipeline`, and
candidate evidence through the canonical live evaluator. Task 8 retains exact
typed child evidence and emits `Task9CycleMarketEvidenceV1` for both markets.

The launcher records retained actual provider throttle incidents, then creates
the Task 9 production runtime. The runtime applies child evidence authority,
PAPER planning/lifecycle/reconciliation, and the Task 9 counting evaluator.
The runner persists the receipt before its lazy, non-authoritative dashboard
publication callback.

## Intended authorities

| Responsibility | Intended authority |
|---|---|
| Market identity | `market_spec_for` and certified cycle contracts |
| Angel certification client | `services.broker.shared_client.get_certification_market_client` |
| Historical candles | `LiveMultiTimeframeData` |
| Historical cache/gate/cooldown | `HistoricalDataCache`, `HistoricalRequestGate`, `HistoricalProviderCooldown` |
| Quotes | `fetch_canonical_two_market_full_quotes` |
| Options/Greeks | `LiveOptionDecisionPipeline` / `LiveOptionChainBuilder` |
| Task 8 parent | `run_authoritative_two_market_parent_cycle` |
| Task 8 -> 9 handoff | `Task9CycleMarketEvidenceV1` |
| Provider incidents | Task 8 retained diagnostics + `Task9ExternalProviderBlockerStore` |
| Task 9 counting | `evaluate_task9_live_paper_trade_counting` |
| Progress/read model | Task 9 progress builder; never dashboard |
| Dashboard | `DashboardPublicationStore`, read-only publication |

## Safety boundary

Every active Task 9 contract validates `execution_mode="PAPER"`,
`broker_order_submission=False`, and `live_execution_eligible=False`. The only
identified broker-submit implementation is the legacy generic
`services/core/trading_engine.py` → `services/execution/order_manager.py` path;
it is not imported by the Task 9 launcher/composition.

## Provider governance

Task 9 historical reads use cache before cooldown before durable gate before
`get_historical_data`. The launcher explicitly injects a five-second gate
interval into Task 8 production composition. Quotes, FULL quotes, option data,
and Greeks remain separate endpoint categories.

The legacy `CompletedCandleService` can call historical data directly when the
legacy full `LiveOptionDecisionPipeline` falls back from already-fetched
analysis candles. R2 structurally isolates it: Task 8/9 `capture_option_inputs`
does not instantiate it, and the root option CLI is pinned to the canonical
service rather than exposing the former legacy rollback environment switch.
R3 migrated that direct compatibility request to the shared durable historical
cooldown and request-gate files before its one provider call. It remains a
compatibility API, but is no longer a supported historical safety bypass.

`services.market.historical_market` is an unsupported legacy compatibility
module with no production caller (only its local legacy test).  Task 8/9's
static isolation boundary prohibits importing it; certified historical reads
remain solely with `LiveMultiTimeframeData`.

Angel sessions are locally date-bound: before each authenticated request the
shared client discards any in-memory session created on an earlier
`Asia/Kolkata` calendar date and performs its normal fresh login path.  A
prior-day refresh token is never retained across that boundary.

Certified FULL/LTP market quote requests use a conservative one request per
second endpoint interval.  This is separate from Task 9's five-second
historical interval.  Read endpoints reject successful envelopes with
`data: null` or documented string `data: "null"`; this is endpoint-specific
and does not impose a global mutation-response rule.

## Final compatibility boundary

**CERTIFICATION DATA:** Angel/canonical certified path only. Task 8/9, Task 9
publication/read models, current PAPER lifecycle, and future replay must not
use `services.market_data`.

**RESEARCH/LEGACY DATA:** `services.market_data` is yfinance-only legacy
research compatibility. `dashboard/home.py` is its legacy UI page. The current
Streamlit entrypoint is explicitly `app.py -> dashboard.dashboard_v2.home`.

There is **no automatic cross-provider fallback**. Angel/certification failure
remains unavailable/incident evidence; it never falls back to yfinance. Task 9
dashboard state is read-only and derives from authoritative persisted
certification state only.
