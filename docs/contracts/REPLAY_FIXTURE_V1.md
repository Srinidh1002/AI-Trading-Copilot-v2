# Replay Fixture v1

`ReplayFixtureV1` provides deterministic, offline acceptance replay for the canonical runtime pipeline. It is a saved `MarketSnapshotV1` plus explicit expected `FinalDecisionV1` outcomes. It does not capture market data, invoke providers or brokers, prepare paper trades, execute trades, or persist runtime state.

## JSON shape

```json
{
  "schema_version": "replay_fixture.v1",
  "fixture_id": "nifty-neutral-wait",
  "name": "Neutral NIFTY snapshot stays analysis-only",
  "description": "Optional human context",
  "tags": ["nifty", "offline"],
  "snapshot": { "schema_version": "market_snapshot.v1" },
  "expectations": {
    "action": "WAIT",
    "authorization_status": "ANALYSIS_ONLY",
    "execution_status": "NOT_REQUESTED",
    "direction": "NEUTRAL",
    "validation_passed": true,
    "data_health_status": "VALID",
    "blocking_reasons": [],
    "internal_errors": []
  },
  "metadata": {}
}
```

`snapshot` must be a complete `MarketSnapshotV1.to_dict()` payload. `expectations` may specify any subset of the listed fields; omitted or `null` fields are not checked. Unknown expectation fields are rejected, preventing accidental non-deterministic acceptance assertions.

## P3-1B expectation coverage

In addition to the P3-1A compatibility fields, fixtures may assert `expected_action`, `expected_direction`, `expected_authorization`, `expected_execution_status`, `expected_data_health_status`, `expected_validation_passed`, `expected_market_regime`, `expected_trend_strength`, `expected_volatility_state`, `expected_option_type`, and `expected_trade_plan_present`.

Collection expectations (`expected_blockers`, `expected_missing_sources`, and `expected_stale_sources`) are normalized case-insensitively, ignore order, require each expected item to exist, and allow additional actual values. Score and confidence ranges are inclusive: `confidence_min`/`confidence_max`, `technical_score_min`/`technical_score_max`, `options_score_min`/`options_score_max`, and `institutional_score_min`/`institutional_score_max`.

## Deterministic checks

Replay compares only stable `FinalDecisionV1` fields. Generated decision IDs and run timestamps are intentionally excluded. Missing actual values required by an assertion produce `INSUFFICIENT_DATA`; mismatches produce `FAIL`. Unconfigured expectations are not checked, including an empty expectation object.

Use `load_replay_fixture(path)` to parse JSON and `run_replay_fixture(fixture)` to run the existing canonical pipeline. `run_replay_directory(path)` processes matching JSON files in sorted filename order, isolates malformed files as `ERROR` results, and returns `ReplaySuiteResultV1`. A custom `pipeline_runner` is supported for focused unit tests; production replay uses `run_canonical_pipeline`.

## Synthetic scenario fixtures

`tests/fixtures/replay/` contains NIFTY and SENSEX bullish, bearish, neutral, conflicted, stale, invalid, missing-5m, missing optional-source, high/low-volatility, and market-closed scenarios. Every one is synthetic and includes:

```json
"metadata": {"synthetic": true, "purpose": "offline deterministic replay coverage"}
```

They are not exchange captures. Directional and regime-sensitive tests use explicit injected canonical dependencies or deterministic test runners; no Python or executable configuration is embedded in fixture JSON.
