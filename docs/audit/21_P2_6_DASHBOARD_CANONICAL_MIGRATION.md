# P2-6 — Dashboard Canonical Analysis Migration

## Dashboard-path audit

`app.py` initializes Streamlit session-state values and invokes
`dashboard.dashboard_v2.home`. The fragment obtains its market payload through
`services.market_snapshot.get_market_snapshot`; before P2-6 it passed that
payload directly to `services.trade.trade_engine.analyze_trade`.

Dashboard rendering consumes legacy trade fields including decision,
confidence, institutional score, grade, execution action, bull/bear scores,
trend, pattern, support/resistance, plan fields, risk display, and reason.
`app.py` writes only Streamlit session state. The dashboard fragment reads
validation statistics and decision history from existing services/database code,
but does not call `execute_paper_trade` or `process_trade`. The legacy snapshot
acquisition continues to own its existing market/broker-provider behavior.

## Migration point and implementation

The smallest safe point is immediately after the legacy snapshot is acquired.
`services.dashboard.dashboard_analysis_service.DashboardAnalysisService` now
owns analysis-mode selection, canonical adaptation/pipeline invocation, the
legacy rollback path, compare diagnostics, and a display-only presentation
adapter. `dashboard/dashboard_v2.py` no longer imports or calls
`analyze_trade` directly.

## Mode and rollback

`DASHBOARD_ANALYSIS_MODE` is a narrow non-secret migration setting. The default
is `canonical` because the existing snapshot adapter can run without dashboard
startup-time provider/client construction. `legacy` is the explicit rollback.
`compare` keeps canonical output official and runs legacy analysis only to
produce diagnostics.

## Safety

Canonical/compare conversion or analysis failure does not fall back to a
directional legacy result. The dashboard receives no decision presentation and
shows a safe unavailable state. Canonical output continues to be
`ANALYSIS_ONLY`, `NOT_REQUESTED`, and plan-free. No paper, broker-order,
database-write, or execution function was added or called.

## Files changed

- `services/dashboard/__init__.py`
- `services/dashboard/dashboard_analysis_service.py`
- `dashboard/dashboard_v2.py`
- `tests/test_dashboard_canonical_analysis_service.py`
- `docs/contracts/DASHBOARD_CANONICAL_MIGRATION_V1.md`
- `docs/audit/21_P2_6_DASHBOARD_CANONICAL_MIGRATION.md`
- `docs/CHANGELOG.md`

## Verification status

Per P2-6 instructions, no pytest, coverage, lint, formatting, Streamlit, or
external service was run. The project owner must manually run focused dashboard
migration tests and the configured suite.
