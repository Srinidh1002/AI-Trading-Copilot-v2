# P6I implementation plan

## Minimal architecture

Create a separate PAPER-only `CapitalQuantityPlanningPolicyV1`, `CapitalQuantityPlanningInputV1`, and `CapitalQuantityPlanningResultV1`; keep P6H affordability authoritative. The input references exact typed `CanonicalTradePlanInputV1`, `TradePlanningPolicyV1`, entry/stop/target results, and selection result. It adds only an explicit risk-model choice and the required supplied risk evidence when premium-at-risk is not selected.

## Proposed input contract

Required references: canonical trade-plan input, trade-planning policy, entry result, stop result, target result, selection result, caller-supplied planning IDs, aware timestamp, source timestamps and JSON-safe immutable metadata. Require canonical identity/direction/right, policy IDs, PAPER mode, and READY/coherent upstream statuses to agree. Optional new values: `maximum_capital_utilization_fraction: float | None`, `reserved_capital: float | None`, `per_lot_risk_amount: float | None`, `option_stop_premium: float | None`, and `target_allocation_weights: tuple[float, float, float] | None`; only one explicit approved risk evidence path may be set.

## Proposed result contract

Identity: planning result ID, trade plan ID, policy ID, option selection result ID, canonical identity/right. Status: `READY | BLOCKED | NO_SIZE`, tuples for blockers/reasons/warnings. Capital: available/deployable/reserved capital and utilization fraction. Risk: risk budget, per-lot risk, risk lot limit. Affordability: one-lot cost and upstream affordable limit. Final fields: planned lots, lot size, quantity, premium outlay, risk amount. Optional nested target allocations contain target number, allocation fraction, lots and quantity.

For READY, all final sizing fields are complete and quantity equals lots times lot size. For BLOCKED all sizing groups are absent. For NO_SIZE upstream/capital/risk evidence may remain present, but planned lots and quantity are zero or absent as one wholly specified contract group; prefer zero lots and zero quantity only if the contract defines this explicitly.

## Stages

1. Audit certification: contract-only tests for field validation, serialization, PAPER isolation.
2. Policy/input contracts: no arithmetic beyond coherence and risk-model selection.
3. Result contract: status groups and target-allocation record.
4. Pure evaluator: premium-at-risk only; reuse P6H affordability and apply deterministic minima.
5. Optional target allocation: only after explicit policy behavior and integer remainder tests.
6. Replay certification and cross-P6 regressions.

## Compatibility rules

Do not modify P5/P6E/P6F/P6G/P6H behavior. No production quantity reaches paper execution; P6I produces a plan only. Any later execution adapter must independently consume a typed approved result and revalidate runtime conditions.
