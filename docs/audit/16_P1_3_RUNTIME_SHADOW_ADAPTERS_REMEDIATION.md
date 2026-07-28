# P1-3 Runtime Shadow Adapters Remediation

## Audited paths and integration point

Dashboard remains `app.py -> dashboard/dashboard_v2.py -> services.market_snapshot.get_market_snapshot -> services.trade.trade_engine.analyze_trade`. Its legacy snapshot supplies symbol, OHLCV, price summary, timestamp/status and option analysis; the response supplies display decision, approval flags, scores, plan fields, and nested raw data. Live option remains `live_option_decision_nifty.py -> LiveOptionDecisionPipeline.analyse`, producing session/data statuses, directional lifecycle statuses, optional plan/contract and audit output.

The behavior-neutral integration point is the new explicit `services/contracts/runtime_adapters.py`. It is not wired into either runtime. A future diagnostics caller may invoke it after a legacy result is built, with no provider/broker/paper/database call and no change to the official output.

## Mapping results

Clean mappings: dashboard lowercase OHLCV and price summary; BUY CE/BUY PE; WAIT/HOLD; live market/data blocking statuses; validated plan fields; reason, confidence, decision and institutional scores. Lifecycle mapping is conservative: TRADE_READY is manual approval only with known direction and valid plan; TRADE_ALLOWED is paper-ready only with valid plan and explicit legacy approval fields. Unknown or directionless statuses block.

Unresolved legacy information includes complete identity, snapshot IDs, VIX/FII-DII/source health, stable score scales, and a uniform authorization meaning. The adapter records diagnostics and never claims equivalence. Mapping errors are contained and cannot affect legacy behavior.

## Verification

The focused P1-3 adapter matrix, P1 contracts, and P0 safety tests passed 133 tests with two existing third-party SSL deprecation warnings. Relevant dashboard, paper, audit, and live-option tests produced 251 passes and the existing injected-client constructor failure. The full suite collected 2,748 tests: 2,737 passed, 11 failed, 0 skipped, and 2 warnings in 14.91 seconds. The 11 failures exactly match the P1-2 baseline: broker empty-response/cache expectations, `LiveAnalysisPipeline` constructor mismatch, six `LiveMultiTimeframeData(cache=...)` constructor mismatches, and injected-client wiring in `LiveOptionDecisionPipeline`.
