# Runtime and Data Flow

## Verified dashboard flow

`app.py` initializes Streamlit state and calls `dashboard.dashboard_v2.home()`. The fragment calls `services.market_snapshot.get_market_snapshot()` through `services.utils.safe_execute`, then `services.trade.trade_engine.analyze_trade(snapshot)`.

`services/market_snapshot.py:_build_market_snapshot` calls `services.market.market_data_manager.market_data_manager`, lowercases columns at line 65, calculates indicators, executes smart-money analysis and option-market/LTP integrations, then returns an untyped dict. `services/trade/trade_engine.py:analyze_trade` calls the *other* `services.core.market_snapshot.get_market_snapshot` only when no argument is supplied; with dashboard input it applies `services.decision.master_decision_engine.make_decision`, `services.risk.risk_engine.calculate_risk`, `TradeScoreEngine`, root `services.confidence_engine.calculate_confidence`, `make_master_decision`, response building, and `process_trade`.

Severity: CRITICAL. Exact risk: this route is separate from the live safety pipeline and invokes paper processing. Recommendation: route dashboard through the canonical final response and make paper execution an explicit command. Confidence: VERIFIED.

## Verified live option route

`live_option_decision_nifty.py` imports and calls `services.live_option_decision_pipeline.LiveOptionDecisionPipeline`. `analyse()` validates spot/session, calls `LiveAnalysisPipeline.analyse()`, evaluates setup/candle/breakout, builds option chain after authorization, selects contract, optionally builds a trade plan, records `DecisionAuditTrail`, and returns statuses including `MARKET_CLOSED`, `MARKET_HOLIDAY`, `STALE_MARKET_DATA`, `NO_TRADE`, waiting states, `TRADE_READY`, `TRADE_ALLOWED`, and `TRADE_REJECTED` (lines 908-919).

`services/live_analysis_pipeline.py:LiveAnalysisPipeline.analyse` obtains 5m/15m/1h/1d data, explicitly converts it to uppercase for technical and multi-timeframe analysis and lowercase for candlestick/volume/chart/market structure analysis, then selects a strategy. Its stated scope is read-only; it does not itself place orders.

## Coverage of required stages

| Stage | Dashboard | Live option route |
|---|---|---|
| data / normalization | ad-hoc snapshot; lowercasing | multi-timeframe; explicit upper/lower adapters |
| technical, structure, candle, volume | present, different engines | present |
| option chain / contract | snapshot option analysis, unverified gates | chain then contract selection after setup |
| VIX/FII-DII | legacy master engine imports analyses; runtime completeness UNKNOWN | no verified calls in `LiveAnalysisPipeline` |
| confidence / trade score / risk | multiple legacy engines | strategy, candidate, plan gates |
| final decision / response / audit | response builder; decision-log UI read | structured audit trail/persistence option |
| paper trading | automatically invoked in dashboard analysis | CLI includes paper orchestration |
| live execution | UNKNOWN | explicitly read-only pipeline; no order placement verified |

Recommendation: one flow from validated provider to normalized `MarketSnapshot`, analyses, gates, risk/contract, `FinalDecision`, audit, then UI/paper adapters. Confidence: VERIFIED where stated; UNKNOWN otherwise.
