# Repository Inventory

## Classification

| Classification | Evidence / locations | Target classification |
|---|---|---|
| Active production | `app.py`, `dashboard/`, `services/`, `agents/`, `models/`, `config.py`, `config/`, `settings/` | KEEP WITH FIXES / MIGRATE |
| Possible production | root CLI files (`live_option_decision_nifty.py`, `run_continuous_paper_trading.py`, `live_market_research_runner.py`, etc.) | MIGRATE; callers vary |
| Legacy / compatibility | root wrapper CLIs using `exec(compile(...))`; `daily_research_report_runner.py` wildcard import | RETIRE after migration |
| Archive | `archive/`, including `services_old/`, brokers and former CLIs | RETIRE or MIGRATE selectively |
| Tests | `tests/` (128 files) and root/service `test_*.py` files outside pytest `testpaths` | KEEP; root/service tests are likely uncollected |
| Configuration | `config.py`, `config/`, `settings/trading_config.py`, `.env.example`, `pytest.ini`, `requirements.txt` | MERGE / MIGRATE |
| Data/generated artifacts | `database/ai_trading.db`, `data/decision_snapshots/`, `Day1_Snapshots/`, `logs/`, `reports/`, `__pycache__/` | DATA / GENERATED |
| Documentation | `docs/`, `PROJECT_AUDIT.md`, empty `README.md` | KEEP WITH FIXES |
| Unknown | `agents/` and broad `services/ai`, `backtesting`, `security`, `testing` trees have no verified root runtime caller | UNKNOWN |

Evidence: `rg --files` inventory found 399 production candidates excluding archive, venv, configured tests and root test files. The repository has no uncommitted tracked changes at audit start (`git status --short` empty).

## Entry points

| Kind | Entry point | Verified route / status |
|---|---|---|
| Streamlit | `app.py` | imports `dashboard.dashboard_v2.home`; actual UI path verified |
| Live read-only / paper CLI | `live_option_decision_nifty.py` | imports `LiveOptionDecisionPipeline`, paper-trading services and emits a read-only footer; production invocation not verified |
| Paper CLI wrappers | `run_continuous_paper_trading.py`, `monitor_paper_positions.py`, `paper_trading_preflight.py` | execute archive source at import time; compatibility layer |
| Research/report wrappers | `live_market_research_runner.py`, `daily_research_report_runner.py`, `market_session_summary.py`, `pre_market_readiness.py`, `inspect_audit_log.py` | archive-backed compatibility layer |
| Test-only | `tests/`, plus service/root `test_*.py` | pytest config only collects `tests/` |
| Broker / order execution | `services/execution/`, `services/broker/`, `services/decision/trade_executor.py` | code exists; a live order caller from a supported entry point is UNKNOWN |

Severity: HIGH for entry-point fragmentation. Impact: code existence cannot be equated with runtime use. Recommendation: publish supported commands and remove executable archive wrappers. Confidence: VERIFIED.
