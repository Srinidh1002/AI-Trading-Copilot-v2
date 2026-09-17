# P10-WP2 — P6/P7 Field and Projection Audit

## Objective

Define the authoritative field boundary for plan and position dashboards.

This batch is audit-only. It does not modify Streamlit, P6, P7, P8, P9,
persistence, lifecycle transitions, planning logic, P&L logic, or execution.

## Authoritative source chain

The accepted source chain is:

`TradeOpportunityV1`
→ `ThreeTargetTradePlanV1` or `IntegratedThreeTargetTradePlanResultV1`
→ `NewEntryPaperLifecycleResultV1`
→ `PaperTradePersistenceSnapshotV1`
→ immutable dashboard read models
→ Streamlit rendering

There is no
`services/paper_orchestration/complete_opportunity_cycle_executor.py`
in the repository. P10-WP2 must not require or invent it.

## Authoritative P6 contracts

- `TradeOpportunityV1`
- `ThreeTargetTradePlanV1`
- `IntegratedThreeTargetTradePlanResultV1`

## Authoritative P7 contracts

- `PaperTradeLifecycleStateV1`
- `PaperTradePositionV1`
- `PaperTradeFillV1`
- `PaperTradePnlEvidenceV1`
- `PaperTradePersistenceSnapshotV1`

## P6 opportunity source

### Contract

`services/contracts/trade_opportunity_v1.py`

### Dashboard-safe fields

Identity and timing:

- `opportunity_id`
- `created_at`
- `snapshot_id`
- `decision_id`
- `underlying_symbol`
- `exchange`
- `expiry`

Trade intent:

- `action`
- `directional_bias`
- `option_type`
- `contract_id`
- `trading_symbol`
- `instrument_token`
- `strike`
- `lot_size`
- `reference_option_price`

Scoring and status:

- `technical_strength`
- `option_chain_strength`
- `contract_ranking_score`
- `decision_confidence`
- `opportunity_score`
- `opportunity_status`

Diagnostics:

- `supporting_evidence`
- `contradictions`
- `blockers`
- `warnings`

Safety:

- `execution_mode == "PAPER"`
- `live_execution_eligible is False`

### Projection rule

The dashboard may display these fields but must not:

- reinterpret BUY/SELL/WAIT/HOLD
- recalculate opportunity score
- infer a contract when contract fields are absent
- convert WAIT/HOLD into a trade
- remove blockers or contradictions

## P6 canonical plan source

### Contract

`services/contracts/three_target_trade_plan_v1.py`

### Dashboard-safe fields

Identity and timing:

- `trade_plan_id`
- `trade_plan_input_id`
- `policy_id`
- `selected_opportunity_id`
- `evaluated_at`
- `underlying_symbol`
- `exchange`
- `market`

Status and direction:

- `plan_status`
- `instrument_type`
- `direction`
- `opportunity_confidence`
- `option_confidence`
- `plan_confidence`

Selected contract:

- `selected_option_contract`
- selected option symbol and contract identity from the typed child
- `expiry`
- `days_to_expiry`
- `expiry_category`

Entry:

- `entry_zone_lower`
- `entry_zone_upper`
- `entry_reference_price`
- `entry_tolerance_fraction`
- `maximum_chase_price`
- `entry_method`

Risk:

- `stop_loss_price`
- `stop_loss_method`
- `stop_distance`
- `stop_distance_fraction`
- `risk_amount`
- `maximum_permissible_loss`

Targets:

- `target_1`
- `target_2`
- `target_3`

Sizing and capital:

- `lot_size`
- `lot_count`
- `quantity`
- `available_capital`
- `required_capital`
- `estimated_entry_cost`
- `estimated_exit_cost`
- `estimated_total_charges`
- `estimated_slippage_cost`

Diagnostics:

- `invalidation_rules`
- `blockers`
- `warnings`
- `decision_reasons`

Safety:

- `execution_mode == "PAPER"`
- `live_execution_eligible is False`

### Projection rule

The dashboard must display the typed plan as supplied. It must not:

- calculate entry, stop, targets, RR, quantity, charges, or expiry
- reconstruct a plan from the legacy dashboard trade dictionary
- show a READY card when `plan_status` is BLOCKED or NO_TRADE
- infer missing optional fields
- collapse blockers, warnings, and decision reasons into one message

## P6 integrated plan source

### Contract

`services/contracts/integrated_three_target_trade_plan_result_v1.py`

### Dashboard-safe fields

- `integration_id`
- `status`
- `canonical_trade_plan_input`
- `entry_zone_result`
- `stop_loss_result`
- `three_target_result`
- `option_contract_selection_result`
- `capital_quantity_result`
- `blockers`
- `warnings`
- `decision_reasons`
- `execution_mode`
- `live_execution_eligible`

### Projection choice

P10-WP2 must use one explicit adapter boundary:

1. project `ThreeTargetTradePlanV1` when the canonical integrated plan object is
   directly available, or
2. project `IntegratedThreeTargetTradePlanResultV1` by reading its certified
   typed child results.

The adapter must not mix both sources field-by-field during one projection.

## P6 orchestration boundary

### Executor

`services/paper_orchestration/p6_planning_stage_executor.py`

The executor runs the certified planning authorities in deterministic order and
returns `IntegratedThreeTargetTradePlanResultV1`.

P10-WP2 is a reader. It must not call individual P6 evaluators from Streamlit.

## P7 lifecycle source

### Contract

`services/contracts/paper_trade_lifecycle_state_v1.py`

Contract: `PaperTradeLifecycleStateV1`

### Canonical display states

- `PLANNED`
- `WAITING_FOR_ENTRY`
- `OPEN`
- `PARTIALLY_EXITED`
- `CLOSED_TARGET_1`
- `CLOSED_TARGET_2`
- `CLOSED_TARGET_3`
- `CLOSED_STOP`
- `CLOSED_INVALIDATED`
- `CLOSED_SESSION`
- `CLOSED_EXPIRY`
- `CANCELLED`
- `BLOCKED`

### Dashboard-safe lifecycle fields

- `lifecycle_state_id`
- `trade_plan_id`
- `integrated_trade_plan_result_id`
- `lifecycle_policy_id`
- `current_state`
- `previous_state`
- `transition_sequence`
- `last_transition_code`
- `lifecycle_created_at`
- `waiting_for_entry_at`
- `opened_at`
- `partially_exited_at`
- `closed_at`
- `cancelled_at`
- `blocked_at`
- `terminal_reason`
- `terminal_target`
- `is_terminal`
- `blockers`
- `decision_reasons`
- `warnings`

### Projection rule

Streamlit may label and group lifecycle states but must not evaluate legal
transitions or derive the next state.

## P7 position source

### Contract

`services/contracts/paper_trade_position_v1.py`

Contract: `PaperTradePositionV1`

### Dashboard-safe position fields

Identity and instrument:

- `position_id`
- `trade_plan_id`
- `integrated_trade_plan_result_id`
- `selected_option_contract_id`
- `market`
- `exchange`
- `underlying_symbol`
- `option_symbol`
- `direction`
- `option_type`
- `strike`
- `expiry`

Entry:

- `entry_fill`
- `entry_price`
- `opened_at`

Sizing:

- `initial_lot_count`
- `lot_size`
- `initial_quantity`
- `remaining_lot_count`
- `remaining_quantity`
- `target_1_lot_count`
- `target_2_lot_count`
- `target_3_lot_count`
- `runner_lot_count`

Risk and targets:

- `stop_loss`
- `target_1`
- `target_2`
- `target_3`

Capital and P&L:

- `estimated_premium_outlay`
- `estimated_risk_amount`
- `estimated_total_trading_cost`
- `estimated_total_capital_requirement`
- `realized_gross_pnl`
- `realized_net_pnl`
- `unrealized_pnl`
- `total_pnl`

State and evidence:

- `lifecycle_state`
- `exit_fills`
- `blockers`
- `decision_reasons`
- `warnings`

Safety:

- `execution_mode == "PAPER"`
- `live_execution_eligible is False`

### Projection rule

The dashboard must not recalculate:

- remaining quantity
- target allocations
- realized P&L
- unrealized P&L
- total P&L
- trading costs
- capital requirement

## P7 fill source

### Contract

`services/contracts/paper_trade_fill_v1.py`

Contract: `PaperTradeFillV1`

### Dashboard-safe fill fields

- `fill_id`
- `trade_plan_id`
- `position_id`
- `selected_option_contract_id`
- `observation_id`
- `fill_type`
- `fill_reason`
- `side`
- `filled_lot_count`
- `lot_size`
- `filled_quantity`
- `fill_price`
- `gross_notional`
- `estimated_trading_cost`
- `net_cash_effect`
- `filled_at`
- `source`
- `target_name`
- `warnings`

### Projection rule

Exit history must use the persisted fill sequence. Streamlit must not synthesize
fills from lifecycle state or P&L totals.

## P7 P&L evidence source

### Contract

`services/contracts/paper_trade_pnl_evidence_v1.py`

Contract: `PaperTradePnlEvidenceV1`

### Dashboard-safe fields

- `pnl_evidence_id`
- `position_id`
- `trade_plan_id`
- `observation_id`
- `entry_price`
- `current_option_price`
- `initial_quantity`
- `remaining_quantity`
- `exited_quantity`
- `realized_gross_pnl_before`
- `realized_gross_pnl_delta`
- `realized_gross_pnl_after`
- `realized_net_pnl_before`
- `realized_net_pnl_delta`
- `realized_net_pnl_after`
- `unrealized_pnl_after`
- `total_pnl_after`
- `calculated_at`
- `warnings`

### Projection rule

The latest persisted P&L evidence is authoritative. The dashboard may format
numbers but must not recompute them.

## P7/P8 orchestration boundary

### Executor

`services/paper_orchestration/new_entry_paper_lifecycle_executor.py`

The executor consumes a READY integrated P6 plan and coordinates P8 admission,
P7 entry handling, and P7/P8 persistence.

`NewEntryPaperLifecycleResultV1` may return:

- `ADMISSION_BLOCKED`
- `NO_CAPACITY`
- `ENTRY_BLOCKED`
- `WAITING_FOR_ENTRY`
- `ENTRY_CLOSED`
- `OPEN`

The dashboard must render these statuses as supplied and must not call entry or
admission evaluators itself.

## Existing active dashboard debt

`dashboard/dashboard_v2.py` currently:

- renders entry, stop, targets, and RR from a legacy `trade` dictionary
- invokes analysis from the page
- reads legacy paper-trade statistics
- reads SQLite decision history directly
- has no authoritative P6 plan card
- has no authoritative P7 lifecycle/position card
- has no persisted fill timeline
- has no typed P&L evidence rendering

The legacy trade-plan section must be replaced later, not supplemented as a
second competing authority.

## Proposed P10-WP2 read models

- `DashboardOpportunityViewV1`
- `DashboardTradePlanTargetViewV1`
- `DashboardTradePlanViewV1`
- `DashboardPaperFillViewV1`
- `DashboardPaperPositionDetailViewV1`

## Status rendering policy

Plan:

- `READY`: render complete plan
- `BLOCKED`: render blockers; no executable-looking card
- `NO_TRADE`: render reasons; no executable-looking card
- absent: render explicit NO_DATA state

Position:

- pending states: neutral information card
- open/partial states: active PAPER position card
- terminal states: closed PAPER result card
- blocked: blocker card
- absent: explicit no-position state

No status may be rendered as LIVE.

## Batch 1 conclusion

The source contracts contain enough certified information for plan and position
dashboards. No new business computation is needed.

The next implementation batch should add immutable opportunity, target, trade
plan, fill, and detailed position read-model contracts only.
