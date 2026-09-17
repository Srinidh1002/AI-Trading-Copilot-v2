# Offline Canonical Replay

P3-1B expands the additive replay harness into a deterministic, offline NIFTY and SENSEX scenario suite. The only runtime path is a saved `MarketSnapshotV1` through the existing canonical pipeline to `FinalDecisionV1`. No dashboard, production CLI, paper, broker, provider, database, or execution route is changed.

The suite has 24 synthetic fixtures: bullish, bearish, neutral, conflicted, stale, invalid, missing required 5-minute timeframe, missing options, missing institutional data, high volatility, low volatility, and market closed for each index. Optional options and institutional sources remain non-blocking unless the certified canonical output says otherwise. Missing 5-minute data, invalid snapshots, and stale snapshots retain their existing fail-closed behavior.

`run_replay_directory()` loads only matching JSON files in lexical filename order. A malformed or unsupported fixture is represented as an `ERROR` result and does not stop the suite. `PASS` means every configured assertion matched; `FAIL` means an asserted value mismatched; `INSUFFICIENT_DATA` means an asserted actual value was unavailable; and `ERROR` means fixture loading or execution infrastructure failed. Normal `WAIT` or `BLOCKED` decisions are not errors.

Suite serialization is stable, ordered, and finite. `semantic_dict()` excludes the generated suite ID and timestamp. File-level errors use only normalized filenames and never expose absolute paths. Tests use injected canonical dependencies or deterministic pipeline runners when compact JSON alone cannot force a directional/regime-specific outcome.

Current limitations: fixtures are synthetic offline inputs, not historical market captures; the harness validates canonical outcomes but does not capture data, execute decisions, or persist a report. Tests were not run during implementation.
