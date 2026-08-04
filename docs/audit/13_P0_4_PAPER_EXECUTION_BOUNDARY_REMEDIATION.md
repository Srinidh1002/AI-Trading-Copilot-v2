# P0-4 Paper Execution Boundary Remediation

## Root cause

`services.trade.trade_engine.execute_paper_trade` previously trusted `trade_action == "EXECUTE"`, indexed required fields directly, and forwarded the payload to `process_trade`. It could persist an unapproved `WAIT` result and raise `KeyError` for malformed input.

## Caller and contract inventory

No production caller invokes this legacy boundary. Its only direct callers before P0-4 were P0-2/P0-3 tests. `analyze_trade` remains analysis-only. Its response contract supplies `decision`, `master_decision`, `approval_status`, `entry_allowed`, `trade_action`, plan fields, `risk_level`, `snapshot`, and reason.

## Approval predicate

Execution is permitted only when all conditions hold:

1. input and snapshot are mappings;
2. decision maps to a directional BUY/SELL (`BUY`/`BUY CE` or `SELL`/`BUY PE`);
3. `trade_action == "EXECUTE"`;
4. `approval_status == "APPROVED"`, `entry_allowed is True`, and `master_decision` agrees with the direction;
5. no input error flag or rejected/high risk level is present;
6. timestamp/reason are non-empty strings; and
7. entry, stop-loss, targets, confidence, and LTP are positive finite values (and quantity when supplied).

The existing response has no reliable contract-selection status, so uncertain results are rejected rather than inferred safe.

## Result contract

All rejected validation cases and unexpected `process_trade` exceptions return:

```python
{"status": "REJECTED", "executed": False, "reason": "...", "paper_trade": None}
```

Only validated approval calls `process_trade`; success returns `SUBMITTED`, `executed=True`, and the submitted legacy payload. No broker or live-execution component is invoked.

## Verification

P0-3 xfails were converted to normal tests. P0-4 tests cover blocked actions, absent/unsupported action, malformed/missing plan fields, NaN/infinite/quantity validation, authorization/action inconsistencies, internal error/risk rejection, valid approved BUY and SELL, paper-engine exception handling, and repeated rejection. Commands and results are recorded in the task response.

Final verification commands and results:

- `venv\\Scripts\\python.exe -m pytest tests\\test_p0_4_paper_execution_boundary.py tests\\test_p0_3_entry_point_fail_safe_matrix.py tests\\test_dashboard_paper_side_effect_separation.py tests\\test_paper_trading_engine.py tests\\test_paper_trading_orchestrator.py -q`: **160 passed**, 2 third-party deprecation warnings, 2.87 seconds.
- `venv\\Scripts\\python.exe -m pytest -q`: **2,636 passed, 11 failed, 0 skipped, 2 warnings** in 12.76 seconds (2,647 collected). The 11 failures exactly match the P0-3 baseline: broker empty-response/cache expectations, `LiveMultiTimeframeData` constructor expectations, `LiveAnalysisPipeline` constructor expectation, and `LiveOptionDecisionPipeline` data-service expectation. The two P0-3 expected failures no longer exist.
