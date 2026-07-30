# P10A — Dashboard Authority Audit

## Scope

This audit covers the current Streamlit entry point, active dashboard page,
legacy dashboard pages, dashboard presentation helpers, live-data acquisition,
analysis selection, PAPER trade persistence, portfolio persistence, runtime
statistics, refresh behavior, direct database reads, and health diagnostics.

No production behavior is changed by this work package.

## Current entry point

The active application path is:

`app.py`
→ `dashboard.dashboard_v2.home`

`dashboard/__init__.py` is empty and has no authority.

## Dashboard inventory

| File | Classification | Notes |
|---|---|---|
| `dashboard/dashboard_v2.py` | Active UI, mixed responsibility | Renders UI but also acquires data, invokes analysis, reads SQLite, reads legacy PAPER statistics, health, cache, and performance services. |
| `dashboard/home.py` | Legacy UI, non-authoritative | Directly fetches market data and runs technical, AI, summary, and trade recommendation logic. |
| `dashboard/live_market_test.py` | Legacy diagnostic UI, non-authoritative | Directly acquires market snapshots and runs trend, trade, and confidence logic. |
| `dashboard/sidebar.py` | Presentation helper | Streamlit-only; currently accepts arbitrary symbols. |
| `dashboard/widgets.py` | Presentation helper | Streamlit rendering only. |
| `dashboard/charts.py` | Presentation helper | Plotly chart construction only. |
| `dashboard/layout.py` | Presentation helper | Streamlit column layout only. |
| `dashboard/cards.py` | Empty | No authority. |
| `dashboard/styles.py` | Empty | No authority. |
| `dashboard/__init__.py` | Empty | No authority. |

## Active dashboard authority violations

`dashboard/dashboard_v2.py` currently performs responsibilities that must move
behind the P10 read-model boundary:

1. Calls `services.market_snapshot.get_market_snapshot`.
2. Calls `DashboardAnalysisService.analyse`.
3. Converts analysis through `dashboard_trade_presentation`.
4. Reads `database/ai_trading.db` directly with `sqlite3`.
5. Reads legacy PAPER statistics from `services.trade.paper_trade_manager`.
6. Reads process-local history cache state.
7. Reads performance timing state.
8. Reads health diagnostics directly.
9. Owns fallback dictionaries and display-specific error handling for missing
   authoritative state.

These behaviors are tolerated only as the pre-P10 migration baseline.

## Analysis-service finding

`services/dashboard/dashboard_analysis_service.py` is not a passive read-model
service. It can:

- normalize legacy snapshots
- execute canonical analysis
- execute the canonical decision pipeline
- lazily load the legacy trade engine
- compare canonical and legacy results
- produce a legacy dashboard presentation mapping

It remains an analysis integration service. P10 read models may consume its
already-produced result only through an injected source. Streamlit must not
invoke it directly after P10 integration.

## Market-snapshot finding

`services/market_snapshot.py` is a live producer. It performs market-data
acquisition, indicator calculation, smart-money analysis, live LTP access,
option analysis, refresh decisions, and session-time calculation.

It must remain outside the dashboard read-model package.

## PAPER authority finding

`services/trade/paper_trade_manager.py` is legacy mutable SQLite PAPER logic.
Its trade creation, open-trade update, and P&L behavior are not authoritative
after P7/P8/P9 certification.

Authoritative sources are:

- P7: `PaperTradePersistenceService`
- P8: `PaperPortfolioPersistenceService`
- P9: `PaperOrchestrationCycleResultV1`
- Runtime: `ContinuousPaperTradingRuntime.get_stats()`

Legacy trade statistics may remain diagnostic during migration but must be
clearly labeled non-authoritative.

## Health finding

The health implementation is a package, not a single module:

- `services/health/__init__.py`
- `services/health/health_check.py`

`services/testing/system_health.py` is test infrastructure and must not become
the production dashboard authority.

## Read-model source map

| Dashboard concern | Authoritative source |
|---|---|
| Market state | caller-supplied typed market snapshot or certified projection |
| Latest cycle | `PaperOrchestrationCycleResultV1` |
| Opportunity | typed opportunity supplied by the orchestration/result source |
| P6 plan | typed integrated three-target plan supplied by the orchestration/result source |
| Active and closed PAPER positions | `PaperTradePersistenceService` |
| Portfolio capital and risk | `PaperPortfolioPersistenceService` |
| Runner state | `ContinuousPaperTradingRuntime.get_stats()` |
| Validation summary | deterministic aggregation over typed P7 snapshots |
| Legacy DB history | diagnostic-only adapter during migration |

## Locked P10 boundary

P5/P6/P7/P8/P9 typed state
→ injected dashboard read-model sources
→ pure read-model assembler
→ immutable `DashboardSystemSnapshotV1`
→ Streamlit rendering only

## Prohibited Streamlit responsibilities

Streamlit must not:

- fetch market data
- execute canonical or legacy analysis
- rank opportunities
- calculate entry, stop, or targets
- evaluate portfolio admission
- mutate P7 or P8 state
- write orchestration journal records
- read broker clients
- submit, cancel, or modify orders
- generate hidden identities or timestamps for trading authority

## Migration classification

### Keep as presentation code

- `dashboard/layout.py`
- `dashboard/charts.py`
- `dashboard/widgets.py`
- `dashboard/sidebar.py` after symbol allowlist migration

### Replace as active data assembly

- service calls and SQLite reads inside `dashboard/dashboard_v2.py`

### Preserve as legacy/non-authoritative until removal

- `dashboard/home.py`
- `dashboard/live_market_test.py`
- mutable operations in `services/trade/paper_trade_manager.py`

## WP1 completion criteria

WP1 is complete when:

1. this audit is committed
2. the read-model design is committed
3. the audit tests pass
4. no production trading behavior changed
5. the next batch can add immutable read-model contracts without importing
   Streamlit, providers, brokers, or execution modules
