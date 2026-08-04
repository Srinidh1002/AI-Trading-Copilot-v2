# P0-1 Configuration Namespace Remediation

## Root cause

Python resolves the `config/` package before the adjacent root `config.py` module. `utils/debug.py` imports `DEBUG_MODE` from `config`, but `config/__init__.py` only exported version metadata. This produced the verified collection failure.

## Import inventory and public expectations

Direct `from config import` callers expect these names:

- `dashboard/dashboard_v2.py`: `APP_NAME`, `VERSION`, `PHASE`, `BUILD`
- `dashboard/sidebar.py`: `DEFAULT_SYMBOL`
- `utils/debug.py`: `DEBUG_MODE`
- `services/broker/angel_client.py`: `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`
- `services/broker/auth.py`: `UPSTOX_API_KEY`, `REDIRECT_URI`
- `services/broker/token.py`: `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, `REDIRECT_URI`

`live_option_decision_nifty.py` (and its archived counterpart) separately import `CAPITAL`, `RISK_PERCENT`, `ENABLE_PAPER_TRADING`, `PERSIST_PAPER_TRADES`, `BREAKOUT_BUFFER_PERCENT`, `MAXIMUM_CAPITAL_USAGE_PERCENT`, `ENFORCE_MARKET_SESSION`, `MAXIMUM_CANDLE_AGE_MINUTES`, `PERSIST_AUDIT`, and `CONFIRMATION_INTERVAL` from `settings.trading_config`; that module was not changed.

## Compatibility approach

`config/__init__.py` now loads the existing root `config.py` once under an internal module name and re-exports its uppercase constants. It then re-exports the package's pre-existing version metadata (`APP_NAME`, `VERSION`, `PHASE`, `BUILD`) last, preserving the values package callers previously received. No threshold, feature flag, environment-variable name, directory path, decision, risk, broker, execution, paper-trading, or dashboard logic was changed.

Loading `config.py` retains its existing `load_dotenv` and directory-initialisation semantics when callers request its constants; the package adds no independent configuration values or additional business side effects.

## Verification

Commands run:

1. `venv\\Scripts\\python.exe -c "from config import DEBUG_MODE; ..."` — passed.
2. `venv\\Scripts\\python.exe -c "from config import ...; from settings.trading_config import ..."` — all identified public imports passed without printing secrets.
3. `venv\\Scripts\\python.exe -m pytest tests\\test_config_import_compatibility.py -q` — initially 1 passed; expanded compatibility test was then added to verify every non-version root export is value-identical.
4. `venv\\Scripts\\python.exe -m pytest -q` — collection completed: 2,603 passed, 11 failed, 0 skipped, 2 warnings, 12.27 seconds.

The original 14 `DEBUG_MODE` collection errors are eliminated. The remaining failures are outside this change: one empty broker response diagnostic (`tests/test_angel_client_resilience.py`), two broker cache assertions (`tests/test_broker_market_data_control.py`), six `LiveMultiTimeframeData` constructor mismatches, one `LiveAnalysisPipeline` constructor mismatch, and one `LiveOptionDecisionPipeline` data-service expectation. They were not modified.
