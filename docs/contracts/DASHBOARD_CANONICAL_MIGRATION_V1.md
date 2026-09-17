# Dashboard Canonical Migration v1

The dashboard retains its existing market-data acquisition path. Immediately
after a legacy snapshot is available, `DashboardAnalysisService` adapts it to
`MarketSnapshotV1`, runs the additive canonical pipeline, and passes its
`FinalDecisionV1` through `dashboard_trade_presentation` for existing widgets.

## Temporary mode

`DASHBOARD_ANALYSIS_MODE` accepts only:

- `canonical` — default; official dashboard output comes from `FinalDecisionV1`.
- `legacy` — explicit rollback; retains the former `analyze_trade(snapshot)`
  result.
- `compare` — canonical output remains official while a supplied legacy result
  is compared for diagnostics.

The mode is not an authorization, execution, paper-trading, or broker control.
It contains no secrets and is intended for removal after migration certification.

## Safety behavior

The application service does not acquire market data, write a database, invoke
paper execution, or call broker execution. Canonical conversion or analysis
failure produces no legacy directional fallback in canonical/compare mode; the
dashboard displays an unavailable safe state instead. Canonical responses stay
`ANALYSIS_ONLY`/`NOT_REQUESTED` and contain no trade plan.

The existing dashboard history, validation-statistics, health, and rendering
sections remain outside this analysis service. Their prior read-only refresh
behavior is unchanged.
