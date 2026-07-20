# PROJECT AUDIT

> **Audit date:** 2026-07-20  
> **Scope:** Static review of the complete working tree, plus pytest discovery only.  
> **Repository mutation:** This document is the sole file created by the audit. No application, test, configuration, data, or runtime file was changed.

## Executive state

The repository is an AI-assisted Indian-market trading and paper-trading application with a Streamlit entry point, SQLite persistence, Angel/Dhan/Upstox integration code, a large safety-gated live-option pipeline, and a broad test suite. It is currently in an active migration: flat `services/*.py` modules, newer package-oriented modules under `services/*/`, and a complete `archive/` implementation coexist.

Static inventory found **489 Python files**: **300 non-test files** and **189 test/demo files**. Pytest discovers **2,456 tests**, but collection currently ends with **11 errors**; therefore this audit does not claim that the suite is green.

## 1. Complete folder tree

```text
AI-Trading-Copilot-v2/
├── .agents/                         local agent configuration
├── .env, .env.example               environment configuration
├── .gitignore
├── app.py                           Streamlit production entry point
├── config.py                        global constants and environment loading
├── requirements.txt                 pinned runtime dependencies
├── pytest.ini                       pytest discovery configuration
├── README.md                        empty
├── services_structure.txt           historical structure reference
├── project_files.csv                generated file inventory
├── agents/                          thin agent wrappers
├── archive/                         superseded CLIs and v1 engines
│   └── services_old/                archived analysis/risk/trading engines
├── dashboard/                       Streamlit views and widgets
├── data/                            instrument data, audit, cache, journals, reports, snapshots
│   ├── audit/
│   ├── decision_snapshots/2026-07-16/
│   ├── market_data_cache/
│   ├── market_journal/2026-07-17/
│   ├── market_sessions/{2026-07-14,2026-07-15,2026-07-16,2026-07-17,2099-12-31}/
│   └── research_reports/
├── database/                        SQLite database files
├── Day1_Snapshots/                  captured day-one snapshots
├── docs/                            project documentation
├── logs/                            application and raw logs
├── models/                          dataclass-style state models
├── reports/                         generated reports
├── services/                        production and transitional service code
│   ├── ai/                          AI explanation/reporting helpers
│   ├── analysis/                    packaged analysis engines
│   ├── backtesting/                 backtest engine
│   ├── broker/                      broker/auth/client adapters
│   ├── core/                        snapshot schema and constants
│   ├── decision/                    packaged decision engines
│   ├── execution/                   market/trade guards
│   ├── indicators/                  packaged indicators
│   ├── market/                      packaged market-data components
│   ├── options/                     packaged option-analysis components
│   ├── paper_trading/               alternate paper-trade engine
│   ├── risk/                        packaged risk engine
│   ├── scoring/                     market/trade scoring
│   └── trade/                       packaged trade helpers
├── settings/                        trading configuration
├── tests/                           pytest suite (128 files)
└── utils/                           currently empty utility package
```

Root-level `test_*.py` files and embedded `services/**/test_*.py` scripts exist, but `pytest.ini` limits normal collection to `tests/`.

## 2. Python-file inventory

### Status legend

| Status | Meaning |
|---|---|
| Active | Reached directly from the Streamlit production import path. |
| Implemented | Contains production logic but is not reached by the current Streamlit path. |
| Tested | Has a corresponding test module in `tests/`; this does not mean all tests currently pass. |
| Legacy | Flat or superseded implementation retained during migration. |
| Archived | Located under `archive/`; not in the production import path. |
| Test/demo | Test or manual executable script. |
| Empty | No operational implementation. |

The following inventory records each source family, the modules it contains, its purpose, status, imports, and public exports. Imports use package-level dependencies; public exports are the externally relevant functions/classes found by static AST inspection. Test modules are listed in the test-coverage section and are all `test/demo` status.

| Paths / modules | Purpose and status | Main imports | Public exports |
|---|---|---|---|
| `app.py` | **Active.** Streamlit startup, session initialization, DB initialization, dashboard launch. | `streamlit`, `dashboard.dashboard_v2`, `services.database` | module entry point |
| `config.py` | **Active configuration.** Loads `.env`, paths, API credentials, trading/UI defaults. | `os`, `pathlib`, `dotenv` | constants |
| `dashboard/dashboard_v2.py` | **Active.** Current dashboard implementation. | `sqlite3`, `pandas`, `streamlit`, `services.market_snapshot`, `services.trade.trade_engine`, `services.trade.paper_trade_manager` | `load_history`, `load_validation_stats`, `home` |
| `dashboard/{home,sidebar,layout,widgets,cards,charts,styles,live_market_test}.py` | Legacy/alternate dashboard views and presentation helpers. | Streamlit; flat market/trade/AI services; Plotly in `charts` | `home`, `sidebar`, layouts, widgets, charts |
| `agents/{market,technical,timeframe,option,option_contract,options_risk,strategy,risk,market_regime,final_decision,news}_agent.py` | Implemented agent wrappers over analysis/decision services; only `market_agent` and `option_agent` are test-imported. | `models.*`, respective `services.*` engines | one agent class per module |
| `models/*.py` | Implemented typed state containers: market, technical, timeframe, option, contract, strategy, risk, regime, final decision, trade, recommendation. | `dataclasses`, typing | state dataclasses |
| `services/database.py` | **Active.** SQLite schema, connection, decision logging. Performs initialization at import. | `sqlite3`, `pathlib` | `get_connection`, `initialize_database`, `log_decision` |
| `services/market_snapshot.py` | **Active legacy runtime.** Fetches NIFTY candles, calculates legacy indicators, creates dictionary snapshot. | `datetime`, `services.market.live_multi_timeframe_data`, `services.indicator_engine` | `get_market_snapshot` |
| `services/core/{constants,snapshot_schema,market_snapshot}.py` | Implemented newer core snapshot stack. `Snapshot` requires analysis/decision/risk fields not supplied by current factory. | dataclasses, `services.market.live_multi_timeframe_data`, `services.indicators.indicator_engine` | `Snapshot`, `get_market_snapshot` |
| `services/market/{live_multi_timeframe_data,live_market,live_index_price,historical_market,market_snapshot,option_market,instrument_registry,download_master}.py` | Implemented market-data provider, historical/live fetch, instrument and option-market support. | Pandas, broker clients, requests/filesystem | provider/client classes and fetch functions |
| `services/{market_data,market_data_adapter,market_data_validator,market_analyzer,market_engine,market_overview,market_indices,market_score,market_regime_analyzer,market_identity_guard,market_session_configuration,market_session_guard,market_session_summary,market_cycle_journal,market_holiday_calendar,nse_holiday_calendar,bse_holiday_calendar,nse_client,underlying_registry}.py` | Implemented market normalization, validation, session/holiday control, analysis and configuration. Mostly tested but not on active dashboard path. | Pandas, datetime, broker/market modules | validators, analyzers, configuration and registry APIs |
| `services/indicators/{indicator_engine,atr_engine,adx_engine,ema_engine,macd_engine,rsi_engine,vwap_engine}.py` | Implemented packaged indicators. | Pandas, NumPy/`ta` where applicable | `calculate_indicators` and individual indicator calculations |
| flat `services/{indicator_engine,trend_engine,technical,technical_score,technical_analyzer,candlestick_engine,support_resistance_engine,multi_timeframe_engine,multi_timeframe_analyzer,pattern_analyzer,chart_pattern_analyzer,volume_intelligence}.py` | Legacy and transitional technical-analysis implementations. | Pandas and market snapshot/data modules | technical, trend, pattern, indicator APIs |
| `services/analysis/{trend_engine,candlestick_engine,support_resistance_engine,multi_timeframe_engine,market_structure_engine,bos_engine,choch_engine,fvg_engine,liquidity_engine,order_block_engine,smart_money_engine,supply_demand_engine,swing_engine,volatility_engine,volume_engine,option_chain}.py` | Implemented newer analysis package; most modules are not production-imported. | Pandas and packaged analysis modules | trend/pattern/structure engines |
| `services/options/{option_chain_engine,option_flow_engine,option_levels_engine,oi_engine,oi_change_engine,pcr_engine,max_pain_engine,market_structure_engine,snapshot_manager,instrument_search,angel_option_client}.py` | Implemented packaged option-chain and contract analysis. `angel_option_client` deliberately raises `NotImplementedError` for its abstract operation. | broker clients, market option modules, collections | option engine classes/functions |
| flat `services/{option_analyzer,option_ai,option_chain_live,option_chain_validator,option_contract_selector,options_risk_engine,live_option_chain_builder}.py` | Implemented option selection, safety, validation and trade-plan support. Strong test coverage, not dashboard-reached. | market, broker, validation and risk modules | option analysis, selection, risk APIs |
| `services/{strategy_selector,strategy_engine,strategy_library,strategy_regime_performance,setup_trigger_engine,breakout_confirmation_engine,regime_indicator_builder,regime_aware_evidence}.py` | Implemented strategy selection, trigger confirmation and regime evidence. | analysis, options, risk/market structures | selector/strategy/trigger APIs |
| `services/{risk_engine,risk_management_engine,risk_manager,trade_level_engine,trade_plan_engine}.py`; `services/risk/risk_engine.py` | Implemented risk and trade-level planning, with duplicate generations. | math, option/market/trade modules | risk evaluation and level/plan builders |
| `services/{decision_engine,unified_decision_engine,decision_snapshot,decision_explanation,decision_audit_logger,decision_audit_trail,decision_evolution_analyzer}.py`; `services/decision/{decision_engine,master_decision_engine,confidence_engine,risk_management,trade_engine,trade_executor}.py` | Implemented competing decision, audit, confidence and execution implementations. | options, analysis, risk, persistence | decision, audit, confidence, execution APIs |
| `services/{trade_engine,paper_trade,paper_trade_repository,paper_trade_validator,paper_trade_journal,paper_trade_lifecycle_audit,paper_trade_monitor,paper_pnl_engine,paper_position_lifecycle_runner,paper_trading_engine,paper_trading_orchestrator,paper_trading_risk_guard,paper_trading_recovery_manager,paper_trading_runtime_adapter,paper_trading_runtime_health,paper_trading_runtime_heartbeat,paper_trading_heartbeat_monitor,continuous_paper_trading_runtime,live_paper_position_monitor,angel_paper_trade_price_provider}.py` | Implemented paper-trading lifecycle, persistence, monitoring and recovery. | datetime, persistence, broker market data, audit services | paper-trading engines, repositories, guards, monitors |
| `services/trade/{trade_engine,paper_trade_manager,decision_logger}.py`; `services/paper_trading/paper_trade_engine.py` | Newer/alternate trade and paper-trade implementation. `services.trade.trade_engine` is used by the active dashboard. | `services.core.market_snapshot`, trade/risk services | `analyze_trade`, trade-management APIs |
| `services/{live_analysis_pipeline,live_option_decision_pipeline,live_readiness_checker,trading_runtime_config}.py` | Implemented safety-gated live analysis and decision pipeline; documented as read-only/no-order placement. | market validation, option chain, trigger, contract, trade plan, audit services | pipeline classes/checkers/configuration |
| `services/{data_normalizer,completed_candle_service,historical_data_cache,historical_context_engine,historical_trade_performance,active_trade_dashboard,live_dashboard_repository,live_dashboard_service,pipeline_performance}.py` | Implemented support, caching, historical, dashboard-data and pipeline monitoring utilities. | Pandas, SQLite/filesystem, copy/datetime | support classes/functions |
| `services/{daily_research_report,daily_research_report_runner,daily_performance_summary,cross_session_research_runner,cross_session_research_intelligence,research_report_archive,research_anomaly_intelligence,research_anomaly_outcome_correlation,research_anomaly_outcome_reliability,research_anomaly_recurrence_intelligence,research_baseline_drift_intelligence,research_evidence_stability_intelligence,blocker_intelligence,session_manifest,session_manifest_updater,session_journal_analytics}.py` | Implemented research/reporting/audit intelligence. Most are tested independently. | persistence, copy, JSON, datetime | report/running/analysis APIs |
| `services/ai/{ai_engine,trading_ai,live_trading_ai,llm_engine,context_engine,prompt_engine,reasoning_engine,summary_engine,explanation_engine,ai_explanation_engine,ai_summary,market_report_engine,learning_engine,sentiment_engine,confidence_engine}.py`; flat `services/{ai_engine,ai_summary,sentiment,news}.py` | Implemented AI/reporting helpers and older AI scoring path. No active dashboard import uses the packaged AI stack. | OpenAI, option/market/decision/risk engines | AI/reporting classes and functions |
| `services/broker/{base_broker,angel_client,dhan_client,dhan_market_data,upstox_client,market,market_data_control,instrument_registry,option_chain,auth,token,session_manager,smart_api_client}.py` | Implemented broker abstraction, authentication, resilience, instruments and market data. | SmartAPI/Dhan libraries, requests, config | broker clients and auth/session APIs |
| `services/backtesting/backtest_engine.py`, `services/scoring/{market_score_engine,trade_score_engine}.py` | Implemented isolated backtest/scoring components. | Pandas/domain data | engine classes/functions |
| `settings/trading_config.py` | Implemented alternate configuration constants. | standard library | configuration constants |
| `utils/{__init__,helpers}.py` | **Empty.** No imports or public exports. | — | — |
| `archive/*.py`, `archive/services_old/*.py` | **Archived.** Historical DB/CLI/live runners and prior analysis/risk/execution engines. | old service stack | legacy functions/classes and CLI `main()` functions |

## 3. Dependency graph

```text
app.py
├── services.database.initialize_database
│   └── SQLite database/ai_trading.db
└── dashboard.dashboard_v2.home
    ├── services.market_snapshot.get_market_snapshot
    │   ├── services.market.live_multi_timeframe_data.LiveMultiTimeframeData
    │   └── services.indicator_engine.calculate_indicators
    ├── services.trade.trade_engine.analyze_trade
    │   └── services.core.market_snapshot.get_market_snapshot
    │       ├── services.market.live_multi_timeframe_data.LiveMultiTimeframeData
    │       └── services.indicators.indicator_engine.calculate_indicators
    ├── services.trade.paper_trade_manager.get_trade_statistics
    └── direct SQLite SELECT from decision_log
```

Important package dependencies:

```text
broker → market data → market validation/snapshot → indicators → analysis
       → options → strategy → risk → decision → trade plan
       → audit/persistence → paper trading → reporting/research
```

Static import cycles are package-initializer cycles: `services.analysis`, `services.core ↔ services.core.market_snapshot`, and `services.decision ↔ services.decision.decision_engine`.

## 4. Working features

“Working” here means implemented and covered by discovered tests; it does not mean live-broker verification or a passing full suite.

- Angel One client login, market-data retry, reauthentication and invalid-response handling.
- Dhan broker response validation.
- Instrument-master retrieval and NIFTY/SENSEX exchange-aware contract discovery.
- Market-data cache/control, schema validation, candle integrity, identity guards, session and holiday guards.
- Completed-candle extraction and freshness checks.
- Technical analysis, market-regime analysis, trend/volume/pattern analysis, breakout confirmation and trigger evaluation.
- Option-chain normalization, PCR/OI/max-pain/option-level analysis, contract selection and option-risk validation.
- Strategy selection and regime-aware evidence.
- Trade-level, risk-budget and contract-lot-size validation.
- Fail-closed live option-decision pipeline behavior, audit persistence and exception safety.
- Paper-trade lifecycle, repository persistence, P&L, recovery, heartbeats, health checks, risk guards and orchestration.
- Research anomaly, readiness, blocker, baseline-drift, evidence-stability and session-journal analytics.

## 5. Partially implemented features

| Feature | Existing implementation | Missing/current limitation |
|---|---|---|
| Streamlit production runtime | `app.py` and `dashboard.dashboard_v2` render market and trade data. | Uses two snapshot/indicator paths and direct dashboard SQL. |
| New package architecture | `services/core`, `indicators`, `analysis`, `market`, `options`, `decision`, `risk`, `trade` exist. | Not the single active runtime; many package modules are disconnected. |
| Core snapshot | `services.core.market_snapshot` builds a typed snapshot. | Its `Snapshot` construction omits required `analysis`, `decision`, and `risk` fields. |
| AI capabilities | OpenAI adapter, prompts, reports and explanations exist. | Packaged AI path is not integrated into the current dashboard runtime. |
| Broker abstraction | Angel/Dhan/Upstox modules and `BaseBroker` exist. | Production dashboard path is Angel-oriented; adapter selection is not centralized. |
| Live trading | A safety-gated decision pipeline exists and documents itself as read-only. | No production order-placement workflow is enabled; `config.py` sets `ENABLE_LIVE_TRADING = False`. |
| Backtesting | `services/backtesting/backtest_engine.py` exists. | No active application/CLI integration is visible. |

## 6. Empty or placeholder files

| File | State |
|---|---|
| `README.md` | Empty. |
| `utils/__init__.py` | Empty package initializer. |
| `utils/helpers.py` | Empty module. |
| `services/options/angel_option_client.py` | Contains an intentional `NotImplementedError`; it is incomplete as a concrete client. |

Exception-swallowing `pass` blocks occur in `historical_data_cache.py`, `completed_candle_service.py`, `paper_trade_monitor.py`, `paper_trade_repository.py`, `session_manifest_updater.py`, `research_anomaly_outcome_correlation.py`, `research_report_archive.py`, and `decision_snapshot.py`; these are operational resilience choices but reduce diagnosability when errors are not recorded.

## 7. Duplicate functionality

| Job | Competing files | Current canonical candidate |
|---|---|---|
| Market snapshot | `services/market_snapshot.py`, `services/core/market_snapshot.py`, `services/market/market_snapshot.py` | `services/core/market_snapshot.py` |
| Indicator aggregation | `services/indicator_engine.py`, `services/indicators/indicator_engine.py` | `services/indicators/indicator_engine.py` |
| Trend analysis | `services/trend_engine.py`, `services/analysis/trend_engine.py` | `services/analysis/trend_engine.py` |
| Multi-timeframe analysis | flat, `services/analysis/`, archived versions | `services/analysis/multi_timeframe_engine.py` |
| Trade engine | `services/trade_engine.py`, `services/trade/trade_engine.py`, `services/decision/trade_engine.py` | `services/trade/trade_engine.py` is currently dashboard-used |
| Risk/trade levels | `risk_management_engine.py`, `trade_level_engine.py`, `decision/risk_management.py` | `services/trade_plan_engine.py` plus `services/risk/risk_engine.py` |
| Decision policy | `decision_engine.py`, `decision/decision_engine.py`, `decision/master_decision_engine.py`, `unified_decision_engine.py` | `services/unified_decision_engine.py` |
| Confidence | flat, `services/ai/`, `services/decision/` confidence modules | one implementation is not yet established |
| Option chain | `option_chain_live.py`, `analysis/option_chain.py`, `options/option_chain_engine.py`, `broker/option_chain.py` | `services/options/option_chain_engine.py` |
| Database | `services/database.py`, `archive/database_v2.py` | `services/database.py` |
| Dashboard home | `dashboard/home.py`, `dashboard/dashboard_v2.py` | `dashboard/dashboard_v2.py` |

## 8. Technical debt

- The working tree contains tracked deletions, modified source files and many untracked replacement packages; source-of-truth status is not frozen.
- `app.py` performs database initialization at import time, which is repeated under Streamlit reruns.
- `dashboard/dashboard_v2.py` fetches data, invokes a trade engine and queries SQLite directly.
- The active dashboard receives one legacy snapshot while its trade engine obtains another core snapshot, allowing duplicated data fetches and potentially inconsistent displayed/decided values.
- `config.py` uses hardcoded NIFTY defaults, interval/period values, paper-trading thresholds, feature flags and debug mode. `services.market_snapshot.py` additionally hardcodes `EXCHANGE = "NSE"` and `SYMBOL_TOKEN = "99926000"`.
- `Snapshot` schema/factory mismatch can fail the newer core runtime.
- Package `__init__.py` re-exports create import-order-sensitive cycles.
- Runtime contracts are mostly mutable dictionaries rather than a single typed contract.
- SQLite paths are relative; dashboard code also duplicates the database path literal.
- The requirements file mixes direct application dependencies and fully pinned transitive dependencies without a project/package manifest.
- Tests use extensive mocks, which validate contracts but do not demonstrate live provider integration.
- Pytest discovery currently reports 11 collection errors, including imports of deleted root-level runner modules such as continuous paper-trading entries.

## 9. Test coverage

### Strongly covered modules/features

The `tests/` directory contains tests for broker resilience, Angel instruments/data, completed candles, market validation/session/identity, live market configuration and routing, option chain/contract/risk, analysis/regime/pattern/volume, strategy/risk/decision, live pipeline safety/audit, paper trading lifecycle/recovery/heartbeats, reporting/research intelligence, agents, and configuration.

### Tested but not production-reached

`services.market_snapshot`, `market_data`, `market_engine`, `market_analyzer`, `market_indices`, `indicator_engine`, `technical`, `technical_score`, `trend_engine`, `trade_engine`, `option_ai`, `option_chain_live`, `nse_option_chain`, `news`, `sentiment`, and `ai_engine` are mainly reached by tests/manual scripts rather than `app.py`.

### No direct pytest coverage found

Examples include `active_trade_dashboard`, `backtesting.backtest_engine`, `daily_performance_summary`, most `services.ai` modules, many `services.analysis` modules, several `services.broker` adapters, `live_dashboard_repository`, `live_dashboard_service`, `pipeline_performance`, `strategy_library`, `risk_manager`, `settings.trading_config`, and `utils.helpers`.

### Discovery status

`pytest --collect-only -p no:cacheprovider` discovered **2,456 tests** and stopped at **11 collection errors**. Tests were not executed for this audit.

## 10. Data flow

```text
Angel market-data client
  → LiveMultiTimeframeData
  → services.market_snapshot (active legacy snapshot)
  → legacy indicator_engine
  → dashboard.dashboard_v2 display

In parallel during the same dashboard cycle:
  services.trade.trade_engine
  → services.core.market_snapshot
  → LiveMultiTimeframeData
  → packaged indicator_engine
  → trade analysis / paper-trade statistics
  → dashboard.dashboard_v2 display

Decision persistence:
  decision/logging services → SQLite database/ai_trading.db → dashboard history query

AI path currently:
  market/options/decision data → services.ai context/prompt/LLM/report helpers
  (not directly connected to the active dashboard runtime)
```

## 11. Current architecture diagram

```text
                         ┌───────────────────────────┐
                         │ app.py / Streamlit          │
                         └─────────────┬─────────────┘
                                       │
                  ┌────────────────────┴────────────────────┐
                  │                                         │
      ┌───────────▼───────────┐                 ┌───────────▼───────────┐
      │ services.database      │                 │ dashboard.dashboard_v2│
      │ SQLite schema/logging  │                 │ display + direct SQL   │
      └───────────────────────┘                 └───────────┬───────────┘
                                                            │
                         ┌──────────────────────────────────┼─────────────────────────────────┐
                         │                                  │                                 │
             ┌───────────▼───────────┐          ┌───────────▼───────────┐        ┌───────────▼───────────┐
             │ legacy market snapshot │          │ packaged trade engine   │        │ paper-trade manager      │
             │ + flat indicators      │          │ + core snapshot         │        │ + SQLite statistics      │
             └───────────┬───────────┘          └───────────┬───────────┘        └───────────────────────┘
                         │                                  │
             ┌───────────▼───────────┐          ┌───────────▼───────────┐
             │ LiveMultiTimeframeData │          │ LiveMultiTimeframeData │
             └───────────┬───────────┘          └───────────┬───────────┘
                         └─────────────────── Angel/broker market data ───────────────────┘
```

## 12. Development progress estimate

Percentages reflect implementation/test maturity visible in the repository, not release readiness.

| Module family | Estimate | Current state |
|---|---:|---|
| Streamlit app and active dashboard | 65% | Functional path exists; boundary and duplicate-data issues remain. |
| Configuration/database | 75% | SQLite and environment setup implemented; startup/config consolidation incomplete. |
| Broker and market data | 75% | Strong tests and multiple clients; runtime selection not unified. |
| Market validation/session controls | 90% | Broad, safety-oriented test coverage. |
| Core snapshot/package migration | 55% | New implementation exists but has schema mismatch and is not canonical runtime. |
| Indicators | 80% | Implemented twice; packaged path is not universally adopted. |
| Technical/market analysis | 80% | Broad engines/tests; duplicate generations remain. |
| Options analysis/contracts | 85% | Strong chain, integrity, selector and exchange tests; concrete Angel option client incomplete. |
| Strategy/risk/trade plan | 85% | Comprehensive tests and fail-closed rules; parallel engines remain. |
| Decision/audit | 80% | Implemented and tested; multiple decision engines coexist. |
| Paper trading | 90% | Lifecycle, persistence, recovery, risk and health checks are extensively covered. |
| Live decision pipeline | 85% | Safety-gated/read-only pipeline has substantial tests; not connected to dashboard. |
| AI/reporting | 55% | Modules exist but are not integrated into active runtime. |
| Research intelligence/reporting | 80% | Extensive independent test coverage; operational integration is limited. |
| Backtesting | 35% | Engine exists; little visible integration/testing. |
| Documentation/utilities | 20% | README and utilities are empty. |
| Archive cleanup/migration closure | 15% | Archive and active duplicates remain. |

## 13. Remaining roadmap

Only modules with visible incomplete, disconnected, placeholder, or migration-blocked work are listed.

- `services/core/snapshot_schema.py` and `services/core/market_snapshot.py` — resolve factory/schema contract mismatch.
- `services/market_snapshot.py`, `services/indicator_engine.py`, `services/trade_engine.py`, `services/trend_engine.py`, and other flat duplicates — migration disposition unresolved.
- `services/options/angel_option_client.py` — concrete implementation pending.
- `services/ai/*` and flat AI modules — active runtime integration unresolved.
- `services/backtesting/backtest_engine.py` — integration and visible test coverage unresolved.
- `dashboard/home.py`, `dashboard/live_market_test.py`, legacy widgets/layouts — production/legacy disposition unresolved.
- `archive/*` and `archive/services_old/*` — archival/removal disposition unresolved.
- Root CLI runner references used by failing test collection — current import paths unresolved.
- `README.md` and `utils/helpers.py` — empty.

## 14. High-priority tasks

1. Restore a clean, reproducible test collection baseline; resolve the 11 collection errors before interpreting test health.
2. Freeze the runtime source of truth for snapshot, indicators, trade engine, decision and risk paths.
3. Resolve the core `Snapshot` schema/factory inconsistency.
4. Eliminate dashboard/runtime disagreement caused by two market-data snapshot paths.
5. Establish one configuration/database startup path and remove repeated import-time initialization behavior.
6. Decide the production status of the package migration versus flat legacy modules.
7. Complete or explicitly retire `services/options/angel_option_client.py`.
8. Decide whether AI/reporting and backtesting are production features; connect or classify them accordingly.
9. Classify/archive/remove obsolete CLIs and duplicate engines after runtime freeze.
10. Populate baseline project documentation and utility purpose.

## 15. Audit limitations

- This is a static/current-working-tree audit; it does not claim live broker connectivity, financial correctness, or test-pass status.
- “Imported” means repository-visible static imports. Dynamic imports, external cron jobs, and direct script execution may create additional reachability.
- No recommendation in this report changes repository state; canonical candidates are documented only to identify currently duplicated behavior.

