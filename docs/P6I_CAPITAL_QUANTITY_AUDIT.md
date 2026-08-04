# P6I Capital and quantity audit

## Scope

This is a PAPER-only design audit. It adds no allocation, sizing, quantity, target allocation, order, or execution behavior.

## Existing authoritative inputs

| Need | Owner and exact field | Type / validation | P6I sufficiency |
|---|---|---|---|
| Capital and risk ceiling | `CanonicalTradePlanInputV1.available_capital`, `maximum_risk_amount`, `maximum_risk_fraction` | required positive `float`; risk amount cannot exceed capital or fraction cap | authoritative capital/risk ceiling |
| P6H affordability | `OptionContractSelectionResultV1.estimated_one_lot_premium_cost`, `affordable_lot_count`, `selected_lot_size`, `selected_premium` | READY requires positive cost and integer affordable count | authoritative current-capital affordability evidence |
| Entry geometry | `EntryZoneEvaluationResultV1.entry_reference_price`, zone, status | optional positive prices; READY geometry complete | underlying/entry planning geometry, not option premium entry |
| Stop geometry | `StopLossEvaluationResultV1.stop_loss_price`, `stop_reference_price`, `stop_distance` | optional positive; READY geometry complete | underlying stop geometry, not option premium risk |
| Targets | `ThreeTargetEvaluationResultV1.target_1..target_3` | READY has 1/2/3 targets and allocations sum to one | target percentages available, not quantities |
| Lots/policy | `TradePlanningPolicyV1.minimum_lot_count`, `maximum_lot_count`, target allocation fractions | typed policy fields | lot bounds and allocation intent |

`OptionContractSelectionInputV1.available_capital` duplicates capital for P6H selection. P6I should treat `CanonicalTradePlanInputV1.available_capital` as canonical and require it to equal the P6H input provenance only when that input is explicitly attached; it must not silently reconcile differences.

## Current policy reuse and gaps

Reusable: `maximum_risk_fraction`, `maximum_risk_amount`, lot bounds, three target allocation fractions, `allow_partial_target_lots`, `minimum_lots_for_three_targets`, `insufficient_target_lot_behavior`, and PAPER controls. Existing policy also contains estimated slippage/brokerage/other-charge fields, but P6I must not use them.

Absent: deployable-capital utilization fraction, reserve capital, a typed option-premium stop, per-lot monetary risk, and a capital-allocation authority. Do not overload stop-distance, target fractions, or charge estimates. Recommend a supplemental `CapitalQuantityPlanningPolicyV1`, rather than altering `TradePlanningPolicyV1`, for utilization/reserve and an explicitly selected risk model.

## Risk conclusion

The current stop result is an underlying/reference-price stop. It cannot truthfully yield option monetary risk: an option premium does not move one-for-one with its underlying. The safest supported first model is **A: premium-at-risk**: `per_lot_risk_amount = estimated_one_lot_premium_cost`. Future bounded alternatives are caller-supplied `option_stop_premium` (model B) or `per_lot_risk_amount` (model C). Do not introduce Greeks, delta, simulations, or inferred premium stops.

## Affordability conclusion

P6I should reuse P6H's `affordable_lot_count` and one-lot cost, not recompute affordability. If a P6I policy introduces a smaller deployable-capital cap, it may calculate a separate deterministic limit and take the minimum; it should block on incoherence with attached P6H capital evidence rather than replace it.

## Target allocation conclusion

Targets provide `target_number`, price, reward/risk, allocation fraction and reason. They do not provide lots or quantity. Initial P6I should defer target-lot allocation unless a new policy explicitly authorizes it. If included, allocate integer lots by policy fractions using floor, then assign remaining lots in target-number order; totals must equal planned lots and zero-lot targets are explicit warnings, not fractional quantities.

## Recommended statuses and diagnostics

Use `BLOCKED`, `NO_SIZE`, `READY`; existing upstream vocabularies do not provide `NO_SIZE`. BLOCKED covers absent/non-READY/coherence/PAPER failures; NO_SIZE covers valid evidence producing zero lots; READY requires at least one whole lot.

Stable blockers: `CAPITAL_PLANNING_BLOCKED`, `CAPITAL_INPUT_MISMATCH`, `CAPITAL_UNAVAILABLE`, `RISK_BUDGET_UNAVAILABLE`, `PER_LOT_RISK_UNAVAILABLE`, `UPSTREAM_ENTRY_NOT_READY`, `UPSTREAM_STOP_NOT_READY`, `UPSTREAM_TARGETS_NOT_READY`, `UPSTREAM_CONTRACT_NOT_READY`, `PAPER_POLICY_MISMATCH`.

Stable no-size reasons: `AFFORDABLE_LOT_LIMIT_ZERO`, `RISK_LOT_LIMIT_ZERO`, `NO_PERMISSIBLE_QUANTITY`. Validation blockers include `CAPITAL_UTILIZATION_INVALID`, `RISK_BUDGET_INVALID`, `PER_LOT_RISK_INVALID`, `LOT_SIZE_INVALID`, and `TARGET_ALLOCATION_INVALID`. Preserve input/upstream blockers first, then capital, risk, affordability, lots, targets; deduplicate by first occurrence.

## Recommended formulas

Only after new explicit utilization/risk-model fields exist:

`deployable_capital = available_capital * maximum_capital_utilization_fraction`

`risk_budget = min(maximum_risk_amount, available_capital * maximum_risk_fraction)`

`risk_based_lot_limit = floor(risk_budget / per_lot_risk_amount)`

`planned_lot_count = min(upstream_affordable_lot_count, deployable_affordable_limit, risk_based_lot_limit, policy_maximum_lot_count)`

`planned_quantity = planned_lot_count * lot_size`; premium outlay and risk are lots multiplied by their per-lot values. No charges, buffers, or final order semantics belong here.

## Deferred

Orders, broker/provider integration, live execution, charges/taxes, partial fills, execution-time revalidation, and risk modelling from underlying stops remain deferred.
