# Test and Safety Gaps

## Test execution

Environment: Windows, Python 3.14.0, virtualenv `venv`, Streamlit 1.59.1, pytest 9.1.1. Command: `venv\\Scripts\\python.exe -m pytest -q`.

Result: **0 tests executed; 14 collection errors; 7.01 seconds; no skip/warning summary emitted.** The suite first fails in `tests/test_angel_client_resilience.py` and related tests with `ImportError: cannot import name 'DEBUG_MODE' from 'config' (config/__init__.py)`, originating at `utils/debug.py:1`. The same root cause blocks Angel client, broker control, live analysis, live option chain/pipeline, audit persistence, exception-safety, fail-closed, and monitor tests. Classification: implementation/environment namespace defect, not a test assertion failure. Confidence: VERIFIED.

`pytest.ini` limits test paths to `tests`; root and service `test_*.py` files were not collected by this command. Their status is UNKNOWN.

## Safety evidence and gaps

The live option pipeline contains explicit session, holiday, stale-candle, invalid spot, setup confirmation, contract and ATR/trade-plan rejection returns (`services/live_option_decision_pipeline.py:908-1537`). This is positive code evidence only; tests that should prove it cannot collect. Thus the assurance that unsafe BUY/SELL cannot escape is **UNKNOWN**.

**CRITICAL:** the dashboard does not call this pipeline and instead builds a trade from legacy engines. Missing/stale/options/VIX/FII-DII/NaN/exception safety for dashboard BUY/SELL has not been traced to a single fail-closed gate. Impact: specification fail-safe requirement is not demonstrated. Recommendation: establish an integration test from every supported entry point that injects each bad input and asserts only `WAIT`/safe response and no paper/live side effect. Confidence: VERIFIED for bypass; UNKNOWN for exact outcomes.

Additional missing verification: invalid instrument/expiry, timestamp conflict, poor liquidity, unacceptable risk/reward, final audit persistence failure, and live execution blocking. No live order placement was verified; availability of a broker executor is not authorization evidence.
