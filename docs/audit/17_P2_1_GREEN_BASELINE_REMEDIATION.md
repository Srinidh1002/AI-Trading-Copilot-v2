# P2-1 — Green Baseline Remediation

## Scope and baseline

This targeted compatibility task repaired the certified P1-3 baseline without
selecting a canonical runtime pipeline, migrating contracts, or changing any
decision, scoring, confidence, risk, option-selection, paper-trading, broker
order, or live-execution rule.

Baseline command:

```powershell
venv\Scripts\python.exe -m pytest -q
```

Baseline result: **2,737 passed, 11 failed, 0 skipped, 2 warnings**.

## Original failure groups and evidence

| Group | Failing tests | Root cause | Evidence used |
| --- | --- | --- | --- |
| Broker normalization/cache | `test_empty_response_is_rejected`, `test_market_data_reuses_short_lived_identical_response`, `test_controller_logs_request_timing_and_cache_outcome` | The request controller's cache methods had been reduced to no-ops; debug output called `.get()` before response validation. | Current tests, `AngelMarketDataClient._validate_response`, controller callers, and the preceding committed controller implementation. |
| Multi-timeframe constructor | Six tests in `tests/test_live_multi_timeframe_data.py` | `cache` and `cache_enabled` constructor compatibility, plus its fresh-cache path, had been removed. | Current fixtures, `HistoricalDataCache` contract tests, runtime callers, and the preceding committed service implementation. |
| Live analysis constructor | `test_live_analysis_pipeline` | `LiveAnalysisPipeline.__init__` accepted no injected data service and ignored the test double. | Runtime caller inventory and the preceding committed pipeline implementation. |
| Live option injected client | `test_default_pipeline_shares_injected_market_client` | Default nested analysis construction did not receive the explicit `market_client`; option-chain and candle services did. | Current pipeline constructor, nested service constructors, test assertion, and previous wiring. |

## Compatibility decisions and fixes

### Broker empty-response and cache semantics

- `None`, `{}`, and `[]` remain rejected by `_validate_response`; they are not
  cached or reported as a successful broker response.
- Non-mapping debug output is now type-safe, so validation produces the
  expected fail-closed error rather than an `AttributeError`.
- A fresh valid cache entry is returned as a defensive copy. A disabled,
  absent, or stale entry is a cache miss and causes the normal broker request.
- Provider exceptions continue through the existing retry/error path; cache is
  not used as an undocumented stale fallback.

### Constructor/API compatibility

- `LiveMultiTimeframeData(client=None, cache=None, *, cache_enabled=None)` is
  supported. The injected cache is stored and used; default construction stays
  compatible and does not make a broker request during construction.
- `LiveAnalysisPipeline(data_service=None)` is supported. The injected service
  is used for `fetch_all`; default construction uses a `LiveMultiTimeframeData`
  service.
- `LiveOptionDecisionPipeline(market_client=...)` now passes that exact client
  into its default `LiveMultiTimeframeData`, option-chain builder, and
  completed-candle service. Explicitly supplied nested services still take
  precedence.

## Files changed

- `services/broker/market_data_control.py` — restored bounded, fresh-only,
  defensive-copy cache behavior and cache observability.
- `services/broker/angel_client.py` — made debug diagnostics safe for invalid
  responses while retaining existing response validation and retry ordering.
- `services/market/live_multi_timeframe_data.py` — restored the optional cache
  compatibility layer and fresh-cache behavior.
- `services/live_analysis_pipeline.py` — restored injected data-service
  construction and use.
- `services/live_option_decision_pipeline.py` — propagated injected market
  client into the default analysis data service.
- `tests/test_angel_client_resilience.py` — added empty mapping/sequence
  rejection coverage.
- `tests/test_broker_market_data_control.py` — added stale-cache coverage.
- `tests/test_live_multi_timeframe_data.py` — asserted injected cache storage
  and constructor-time broker inactivity.
- `docs/CHANGELOG.md` — recorded P2-1.

## Test evidence

1. Focused broker/live tests:

   ```powershell
   venv\Scripts\python.exe -m pytest tests\test_angel_client_resilience.py tests\test_broker_market_data_control.py tests\test_live_multi_timeframe_data.py tests\test_live_analysis_pipeline.py tests\test_live_option_decision_pipeline.py -q
   ```

   Result: **44 passed, 2 warnings**.

2. P0 safety and P1 contracts/runtime adapters:

   ```powershell
   venv\Scripts\python.exe -m pytest tests\test_p0_3_entry_point_fail_safe_matrix.py tests\test_p0_4_paper_execution_boundary.py tests\test_dashboard_paper_side_effect_separation.py tests\test_market_snapshot_v1.py tests\test_final_decision_v1.py tests\test_runtime_contract_adapters.py -q
   ```

   Result: **133 passed, 2 warnings**.

3. Full configured suite:

   ```powershell
   venv\Scripts\python.exe -m pytest -q
   ```

   Result: **2,751 passed, 0 failed, 0 skipped, 2 warnings**.

The remaining warnings are pre-existing third-party SmartAPI SSL deprecation
warnings (`ssl.OP_NO_TLSv1` and `ssl.OP_NO_TLSv1_1`).

## Safety confirmation

No external broker, exchange, OpenAI, news, or other live service was called:
all verification used mocks, injected fakes, or local deterministic tests. No
tests were removed, skipped, marked xfail, or weakened. Trading, decision,
scoring, confidence, risk, option-selection, paper-execution, broker-order,
and live-execution behavior was not changed.
