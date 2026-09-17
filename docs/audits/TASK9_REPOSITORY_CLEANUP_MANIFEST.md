# Task 9 repository cleanup manifest

This is a conservative static manifest. No file is DELETE_SAFE unless every
reference, dynamic import, CLI, persistence, and compatibility condition is
proven absent. That proof was not available for the multi-generation codebase,
so this pass deletes nothing.

| Path/group | Classification | References/relevance | Recommended action |
|---|---|---|---|
| `services/certification/task9_*` | KEEP | Active launcher, runtime, counting, recovery, persistence, reporting. | Keep. |
| `services/market/live_multi_timeframe_data.py` | KEEP | Active certified candle acquisition. | Keep. |
| `services/broker/shared_client.py`, `angel_client.py` | KEEP | Shared certification client. | Keep. |
| `services/live_option_decision_pipeline.py` | KEEP | Active Task 8 option input capture; legacy full analysis remains API compatibility. | Certified capture now lazily excludes the candle fallback. |
| `services/completed_candle_service.py` | ACTIVE_COMPATIBILITY | Direct legacy full-analysis API/tests; no Task 8/9 capture construction. | KEEP: R3 shares canonical cooldown/gate before provider access. |
| `services/market_data.py` | COMPATIBILITY_SUPPORTED | yfinance dashboard/root-diagnostic helper imported by `dashboard/home.py` and root tests; not Angel/Task 9. | Keep isolated from Task 9-facing packages. |
| `services/core/trading_engine.py`, `services/execution/order_manager.py` | UNKNOWN_REQUIRES_REVIEW | Broker-submit capable legacy path. | Keep isolated from Task 9; review before removal. |
| `archive/` | ARCHIVE_CANDIDATE | Historical source and possible import/document references. | Retain pending operator approval. |
| `Day1_Snapshots/` | ARCHIVE_CANDIDATE | Historical audit/recovery relevance. | Retain. |
| `artifacts/canary/`, `artifacts/certification/task8/`, `docs/audits/` | GENERATED_RUNTIME | Explicitly protected evidence. | Retain. |
| Root `phase6_*.log`, `phase6_*.py` | UNKNOWN_REQUIRES_REVIEW | Supervised provider/session diagnostics; no deletion proof. | Operator review. |
| Root `test_*.py` | TEST_FIXTURE | Legacy engine contracts/reference usage. | Keep until subject ownership is retired. |
| Root wrapper CLIs | ACTIVE_COMPATIBILITY | Archive-backed wrappers and tests/docs reference them. | Keep; do not advertise as Task 9 authority. |
| `__pycache__/`, `.pytest_cache/`, `*.pyc` | GENERATED_RUNTIME | Removable development clutter but not deleted in this audit. | Remove only in a separate approved cleanup. |

DELETE_SAFE generated clutter removed (untracked):

- `.pytest_cache/`
- `__pycache__/`

No tracked source, test, archive, documentation, artifact, cache, or official
runtime-evidence file was deleted.

## R2 provider call classification

| Call site | Classification | Notes |
|---|---|---|
| `market/live_multi_timeframe_data.py` | CANONICAL_ACTIVE | Certified cache → cooldown → durable gate → typed provider call. |
| `certification/task9_external_provider_recovery_probe.py` | RECOVERY_PROBE | Explicit one-request, gate/cooldown/lease contract. |
| `completed_candle_service.py` | LEGACY_COMPATIBILITY | Direct historical fallback; structurally excluded from Task 8/9 capture in R2. |
| `diagnostics/india_vix_provider_contract_capture.py` | CANONICAL_DIAGNOSTIC | Diagnostic-only provider contract capture; not Task 9 composition. |
| `market_data.py` | UNKNOWN_REQUIRES_REVIEW | Legacy market interface, no Task 9 import proven. |
| `broker/angel_client.py` | CANONICAL_ACTIVE | Client endpoint wrapper and typed request controller. |

## R2 archive and historical data

`Day1_Snapshots/` contains 57 timestamp-named JSON historical source snapshots;
there are no active Task 9 imports. They are ARCHIVE_CANDIDATE, not disposable
generated output. `archive/` contains 26 historical scripts; root wrappers,
tests, and documentation still reference parts of it, so the group remains
ARCHIVE_CANDIDATE. No individual archive file was proven DELETE_SAFE.

## R4 final compatibility policy

- `services/market_data.py`: LEGACY_RESEARCH_COMPATIBILITY; yfinance only.
- `dashboard/home.py`: LEGACY_UI; it is not imported by `app.py`.
- `app.py -> dashboard/dashboard_v2.py`: CURRENT_PRODUCTION read-only Task 9
  dashboard entrypoint.
- `services/analysis/option_chain.py`: LEGACY_RESEARCH randomized mock option
  helper; excluded from Task 8/9/certification dashboard import surface.

No new DELETE_SAFE source file was proven in R4. Remaining UNKNOWN root phase-6
diagnostic files require operator retention/disposal policy.
