# P10-WP4 — Dashboard Read-Model Design

## Proposed view families

### DashboardMarketOverviewViewV1

Identity, market status, source timestamp, LTP, RSI, bull/bear/neutral scores,
trend, pattern, support/resistance, decision, confidence, grade, execution
display, risk level, reason, warnings, blockers, and PAPER-only flags.

### DashboardOptionIntelligenceViewV1

Status, PCR, bias, flow, confidence, support, resistance, max pain, CE/PE open
interest, ATM Greeks, aggregate Greeks, warnings, blockers, and PAPER-only
flags.

### DashboardValidationSummaryViewV1

Completed PAPER trades, wins, losses, net realized P&L, source identity,
source timestamp, and warnings. Values must come from P7/P8 authority.

### DashboardDecisionHistoryViewV1

Immutable typed rows containing timestamp, action, confidence, reference price,
and source identity. Streamlit must not query SQLite.

### DashboardRuntimeOperationsViewV1

Runtime status, last success/failure, durations, component health observations,
freshness, and warnings. Streamlit must not run health checks.

## Proposed state keys

- `dashboard_market_overview_view_v1`
- `dashboard_option_intelligence_view_v1`
- `dashboard_validation_summary_view_v1`
- `dashboard_decision_history_view_v1`
- `dashboard_runtime_operations_view_v1`

## Forbidden active-dashboard tokens

- `sqlite3`
- `pandas.read_sql`
- `get_market_snapshot`
- `DashboardAnalysisService`
- `dashboard_trade_presentation`
- `get_trade_statistics`
- `performance_monitor`
- `history_cache`
- `safe_execute`
- `health_check`
- direct `database/` paths
- runtime/orchestration/persistence/provider/trading authority imports

Pure renderers may format certified values and display warnings/no-data states.
They may not calculate scores, decisions, P&L, support/resistance, or Greeks.
