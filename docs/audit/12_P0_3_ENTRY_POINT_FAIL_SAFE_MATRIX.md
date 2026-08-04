# P0-3 Entry-Point Fail-Safe Matrix

## Scope and supported entry points

`docs/00_MASTER_SPECIFICATION.md` remains absent; the equivalent `docs/AI_Trading_Copilot_Master_Specification_v0.1.md` was used. Supported entry points were identified by direct production callers, not file existence:

1. **Dashboard analysis** — `app.py -> dashboard/dashboard_v2.py:home -> services.market_snapshot.get_market_snapshot -> services.trade.trade_engine.analyze_trade`.
   Input: ad-hoc snapshot dict (timestamp, LTP, OHLCV-derived fields, indicators). Output: dashboard response dict. P0-2 proves no legacy paper-engine call; it has no broker execution call. Its production import chain currently has unrelated missing `make_master_decision` and `trade_context` symbols, so invalid-input response behaviour is not executable without prohibited fixes.
2. **Live option analysis** — `live_option_decision_nifty.py:854 -> LiveOptionDecisionPipeline.analyse`. Input: exchange, token, underlying, positive spot price and optional capital/session parameters. Output: dict with a decision, market analysis, contract, trade plan, audit trail and audit-persistence status. It is read-only; no order method exists (`tests/test_live_pipeline_fail_closed.py:test_pipeline_remains_read_only`).
3. **Explicit legacy paper boundary** — `services.trade.trade_engine.execute_paper_trade(analysis_result)`. Input: result dict with decision, trade action, plan fields and snapshot timestamp/LTP. Output: the legacy `process_trade` return (currently `None`). It can mutate `paper_trades` through `services.trade.paper_trade_engine.process_trade -> paper_trade_manager.save_trade/update_open_trade` and has no broker/live execution call.

## Observed unsafe escape

**CRITICAL / VERIFIED:** `execute_paper_trade` accepts `{"decision": "WAIT", "trade_action": "EXECUTE", ...}` and forwards it to `process_trade`. `process_trade` authorizes persistence solely from `trade_action == "EXECUTE"`; it does not validate decision approval. The P0-3 expected-failure test records this. A malformed `{}` input raises `KeyError`, returning neither a safe response nor an audit reason (HIGH / VERIFIED). No production fix was made under the verification-only policy.

## Matrix

Legend: PASS = tested safe response/no execution; FAIL = tested unsafe behaviour; PARTIAL = no execution proven but response/reason/audit incomplete; NOT APPLICABLE = no input/feature in that contract; UNKNOWN = cannot verify without fixing unrelated imports or using prohibited live access.

| # | Mandatory scenario | Dashboard analysis | Live option pipeline | Explicit paper boundary |
|---:|---|---|---|---|
| 1 | Missing market snapshot | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE |
| 2 | Empty OHLCV dataframe | UNKNOWN | PARTIAL — analysis exception propagates | NOT APPLICABLE |
| 3 | Missing OHLCV columns | UNKNOWN | PARTIAL — analysis exception propagates | NOT APPLICABLE |
| 4 | NaN critical price | UNKNOWN | PARTIAL — validator path exists; response not proven | NOT APPLICABLE |
| 5 | Invalid/zero spot | UNKNOWN | PASS — raises before analysis/chain | NOT APPLICABLE |
| 6 | Stale candle/snapshot | UNKNOWN | PASS — `STALE_MARKET_DATA`, no chain | NOT APPLICABLE |
| 7 | Conflicting timeframe timestamps | UNKNOWN | UNKNOWN | NOT APPLICABLE |
| 8 | Unsupported/invalid symbol | UNKNOWN | UNKNOWN — provider validation needs isolated contract | NOT APPLICABLE |
| 9 | Invalid expiry | NOT APPLICABLE | PARTIAL — no-contract gate tested; expiry-specific validation unproven | NOT APPLICABLE |
| 10 | Missing option chain | NOT APPLICABLE | PASS — no trade/plan | NOT APPLICABLE |
| 11 | Empty option chain | NOT APPLICABLE | PASS — `NO_TRADE`, no plan | NOT APPLICABLE |
| 12 | Partial option chain | NOT APPLICABLE | PARTIAL — missing contracts key fails closed; field completeness unproven | NOT APPLICABLE |
| 13 | Poor option liquidity | NOT APPLICABLE | UNKNOWN | NOT APPLICABLE |
| 14 | Wide bid-ask spread | NOT APPLICABLE | UNKNOWN | NOT APPLICABLE |
| 15 | Missing India VIX | UNKNOWN | UNKNOWN | NOT APPLICABLE |
| 16 | Missing FII/DII | UNKNOWN | UNKNOWN | NOT APPLICABLE |
| 17 | Technical-analysis exception | UNKNOWN | PARTIAL — exception propagates, no safe response | NOT APPLICABLE |
| 18 | Market-structure exception | UNKNOWN | PARTIAL — contained in analysis exception category | NOT APPLICABLE |
| 19 | Option-analysis exception | NOT APPLICABLE | PASS — no trade authorization | NOT APPLICABLE |
| 20 | Confidence-engine exception | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE |
| 21 | Risk-engine exception | UNKNOWN | PASS — trade-plan exception cannot authorize | NOT APPLICABLE |
| 22 | Response-builder exception | UNKNOWN — broken import prevents execution | NOT APPLICABLE | NOT APPLICABLE |
| 23 | Audit-persistence exception | NOT APPLICABLE | PARTIAL — decision retained, persistence error captured | NOT APPLICABLE |
| 24 | Unacceptable risk/reward | UNKNOWN | PASS — `TRADE_REJECTED` | NOT APPLICABLE |
| 25 | Position/capital limit violation | UNKNOWN | PASS — invalid capital blocks; rejected plan does not authorize | NOT APPLICABLE |
| 26 | Market closed | NOT APPLICABLE | PASS — `MARKET_CLOSED` before analysis | NOT APPLICABLE |
| 27 | Market holiday | NOT APPLICABLE | PASS — `MARKET_HOLIDAY` before analysis | NOT APPLICABLE |
| 28 | Major internal exception | UNKNOWN | PARTIAL — selected exceptions do not authorize, generic response unproven | PARTIAL — malformed input raises |
| 29 | Repeated dashboard analysis | PASS — P0-2 mock/spies prove no paper call | NOT APPLICABLE | NOT APPLICABLE |
| 30 | Explicit execution unapproved/malformed | NOT APPLICABLE | NOT APPLICABLE | FAIL — executes unapproved; malformed raises |

Totals across 90 cells: **PASS 11, FAIL 1, PARTIAL 10, NOT APPLICABLE 44, UNKNOWN 24**. The matrix explicitly distinguishes untested requirements from verified safe behaviour.

## Evidence and side effects

Live-pipeline PASS evidence is in `tests/test_live_pipeline_fail_closed.py`, `tests/test_live_pipeline_exception_safety.py`, `tests/test_live_option_decision_pipeline.py`, and `tests/test_live_pipeline_audit_persistence.py`. These tests use injected mocks and assert chain/planner stages are not called on earlier failure. `LiveOptionDecisionPipeline` has no order-execution adapter. P0-2’s `tests/test_dashboard_paper_side_effect_separation.py` verifies dashboard analysis does not call `process_trade`, including repeated calls and a throwing paper-engine spy.

The dashboard and explicit boundary do not emit a uniform blocking-reason/audit contract. Live pipeline returns `reasons` only on some gates and attaches `audit_trail`; therefore audit/reason completeness is PARTIAL unless a test proves it.

## Required remediation, ranked

1. **P0 / CRITICAL:** make `execute_paper_trade` reject non-approved actions and malformed results with a structured non-mutating response; require a decision/authorization invariant before `process_trade`.
2. **P0 / HIGH:** restore dashboard trade-engine importability (`make_master_decision`, `trade_context`) before certifying dashboard market-data fail-closed behaviour.
3. **P1 / HIGH:** add deterministic normalization/data-quality gates for empty/malformed/NaN/time-conflicting snapshots and require blocking reasons.
4. **P1 / HIGH:** add option expiry/liquidity/spread and VIX/FII-DII fail-closed contracts to the supported live route.
5. **P1 / MEDIUM:** return one safe error response rather than propagating technical/structure exceptions and make audit persistence outcomes explicit.

## Commands and result record

- `venv\\Scripts\\python.exe -m pytest tests\\test_p0_3_entry_point_fail_safe_matrix.py tests\\test_dashboard_paper_side_effect_separation.py tests\\test_live_pipeline_fail_closed.py tests\\test_live_pipeline_exception_safety.py tests\\test_live_pipeline_audit_persistence.py tests\\test_live_option_decision_pipeline.py -q` produced **44 passed, 1 failed, 2 xfailed, 2 warnings** in 3.35 seconds. The sole failure is the pre-existing `test_default_pipeline_shares_injected_market_client` constructor mismatch from the certified baseline. The two xfails intentionally record the verified explicit-paper-boundary unsafe escape and malformed-input gap.
- `venv\\Scripts\\python.exe -m pytest -q` produced **2,608 passed, 11 failed, 2 xfailed, 0 skipped, 2 warnings** in 13.40 seconds (2,621 collected). The 11 failures exactly match the P0-2 baseline: broker empty-response/cache expectations, `LiveMultiTimeframeData` constructor expectations, `LiveAnalysisPipeline` constructor expectation, and `LiveOptionDecisionPipeline` data-service expectation. The two additional xfails are P0-3 evidence, not repaired failures.

No live broker, exchange, OpenAI, or news service was called; all evidence uses mocks or existing deterministic tests.
