# P3-1B — Replay Scenario Coverage

Implemented deterministic offline replay coverage for 12 NIFTY and 12 SENSEX synthetic scenarios. Fixtures are explicitly labelled `synthetic: true` with purpose `offline deterministic replay coverage`; none claims to be an exchange capture.

The directory runner returns `ReplaySuiteResultV1` with deterministic result ordering and PASS, FAIL, INSUFFICIENT_DATA, and ERROR counts. Invalid JSON and unsupported schemas become isolated file-level ERROR results. It has no file writes, network activity, provider/broker/database/paper access, or runtime route integration.

Expectation checks cover the stable decision contract, collection subsets, and inclusive numeric ranges. Missing required actual values are explicit INSUFFICIENT_DATA outcomes. The scenario tests use explicit injected deterministic runners where production default dependencies cannot be reliably configured by compact JSON.

No canonical action, scoring, confidence, risk, option-selection, or lot-size formula changed. No dashboard, CLI, paper, or execution behavior changed. Tests were written but not run.

Manual verification commands:

```powershell
venv\Scripts\python.exe -m pytest tests/test_replay_harness.py -q
venv\Scripts\python.exe -m pytest tests/test_replay_scenario_matrix.py -q
venv\Scripts\python.exe -m pytest tests/test_replay_directory_runner.py -q
venv\Scripts\python.exe -c "from services.replay import ReplaySuiteResultV1, run_replay_directory; print('replay suite import passed')"
```
