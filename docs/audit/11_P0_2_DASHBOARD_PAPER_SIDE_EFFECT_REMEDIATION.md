# P0-2 Dashboard Paper-Trading Side-Effect Remediation

## Root cause and scope

`dashboard/dashboard_v2.py` calls `services.trade.trade_engine.analyze_trade(snapshot)` during its refresh fragment. Before this change, `analyze_trade` built a legacy paper-trade payload and called `services.trade.paper_trade_engine.process_trade`; its return value was discarded. That call can insert an open trade or update/close an existing trade through `services.trade.paper_trade_manager`.

## Caller audit

- Analysis-only: `dashboard/dashboard_v2.py` is the only production importer of `services.trade.trade_engine.analyze_trade`; `dashboard/live_market_test.py` and root `test_trade_engine.py` use different legacy `services.trade_engine.analyze_trade` implementations.
- Explicit paper execution: `live_option_decision_nifty.py` calls `PaperTradingOrchestrator.process_decision`; continuous paper-trading runtime and lifecycle runners use their own engines. None import this legacy `process_trade` function.
- Background monitoring: `services/paper_position_lifecycle_runner.py:process_trade` is a separate method.
- Tests: orchestrator and lifecycle tests exercise their separate paper paths; the P0-2 tests cover this legacy dashboard path.

## Separation

`analyze_trade` still calculates the same snapshot, decision, risk, score, confidence and response, but does not call the paper engine. The new explicit boundary is `services.trade.trade_engine.execute_paper_trade(analysis_result)`. It derives the exact legacy payload from an already-produced response and invokes `process_trade` only when an intentional caller invokes it. No dashboard imports or calls this boundary.

The old `process_trade` return value was not used by `analyze_trade`; therefore removing that call does not alter the analysis response contract.

## Validation

Focused tests verify no paper-engine call for analysis, no repeated-analysis call, optional paper-engine exceptions cannot affect analysis, explicit submission invokes the engine, and dashboard source contains no execution boundary. Full-suite results are recorded in the task response.

The focused test uses temporary, restored test-only import shims for the pre-existing missing `make_master_decision` export and missing `services.trade.trade_context` dependency expected by `services.trade.trade_engine`. Individual tests replace both dependencies with controlled fakes. These unrelated decision/response import defects are not changed by P0-2.

Executed results:

- `venv\\Scripts\\python.exe -m pytest tests\\test_dashboard_paper_side_effect_separation.py tests\\test_paper_trading_engine.py tests\\test_paper_trading_orchestrator.py -q`: 132 passed, 2 third-party deprecation warnings, 2.87 seconds.
- `venv\\Scripts\\python.exe -m pytest -q`: 2,608 passed, 11 failed, 0 skipped, 2 warnings, 13.18 seconds. The same 11 broker-cache/empty-response and live-pipeline constructor failures from the P0-1 baseline remain; no new product failure was introduced. The pass count increased from 2,603 because the P0-1 compatibility test gained one case and P0-2 added four focused cases.
