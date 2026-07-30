# P10-WP2 — Plan and Position Dashboard Certification

## Scope

P10-WP2 replaces the active dashboard's legacy plan rendering with certified,
typed P6/P7 read models and presentation-only components.

## Completed deliverables

### Read models

- `DashboardOpportunityViewV1`
- `DashboardTradePlanTargetViewV1`
- `DashboardTradePlanViewV1`
- `DashboardPaperFillViewV1`
- `DashboardPaperPositionDetailViewV1`

### Projection adapters

- `project_trade_opportunity`
- `project_three_target_trade_plan`
- `project_paper_trade_fill`
- `project_paper_trade_position_detail`

### Presentation components

- `render_opportunity_card`
- `render_trade_plan_card`
- `render_paper_position_card`
- `render_plan_and_position_dashboard`

### Active dashboard integration

`dashboard/dashboard_v2.py` now:

- reads already-projected P6/P7 views from session state
- renders the certified plan and position section
- removes the legacy entry, stop, target, and RR block
- does not recalculate plan, lifecycle, quantity, or P&L values

## Authority boundary

The dashboard reads:

- P6 opportunity from `TradeOpportunityV1`
- P6 plan from `ThreeTargetTradePlanV1`
- P7 fill history from `PaperTradeFillV1`
- P7 detailed state from `PaperTradePersistenceSnapshotV1`
- P7 P&L from persisted `PaperTradePnlEvidenceV1` when available

The dashboard does not treat the legacy trade dictionary as an authority.

## Safety guarantees

- PAPER-only flags are preserved
- LIVE execution is not enabled
- no broker calls are introduced
- no provider calls are introduced
- no lifecycle mutation is introduced
- no planning computation is introduced
- no P&L computation is introduced
- no SQLite access is introduced in WP2 components or state boundary

## Display guarantees

- READY plans render T1, T2, and T3 in order
- BLOCKED plans render blockers without executable-looking targets
- NO_TRADE plans render decision reasons
- pending positions render neutral state
- active positions render persisted size, risk, and P&L
- terminal positions render terminal evidence
- persisted fill order is preserved
- missing typed views render explicit no-data messages

## Deferred work

P10-WP2 does not remove the remaining legacy dependencies from
`dashboard/dashboard_v2.py`, including:

- market snapshot acquisition
- dashboard analysis invocation
- SQLite decision-history reads
- legacy validation statistics
- existing performance, refresh, and health rendering

Those items remain for later P10 work packages.

## Completion gate

P10-WP2 is complete when:

1. all P10-WP2 tests pass
2. the complete P10 focused suite passes
3. `git diff --check` passes
4. the changed files compile
5. the full repository suite remains green
6. the completed package is committed with a clean working tree
