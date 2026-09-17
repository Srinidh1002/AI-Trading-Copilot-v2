from __future__ import annotations

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)

from .dashboard_trade_plan_target_view_v1 import (
    DashboardTradePlanTargetViewV1,
)
from .dashboard_trade_plan_view_v1 import DashboardTradePlanViewV1


def _first(value: object, *names: str) -> object | None:
    if value is None:
        return None
    for name in names:
        candidate = getattr(value, name, None)
        if candidate is not None:
            return candidate
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _targets(value: object) -> tuple[DashboardTradePlanTargetViewV1, ...]:
    if getattr(value, "status", None) != "READY":
        return ()

    result = []
    for number in (1, 2, 3):
        target = getattr(value, f"target_{number}")
        result.append(
            DashboardTradePlanTargetViewV1(
                target_name=f"T{number}",
                target_price=target.target_price,
                reward_amount=_first(target, "reward_amount"),
                reward_to_risk=_first(
                    target,
                    "reward_to_risk",
                    "reward_risk_ratio",
                ),
                booking_fraction=_first(
                    target,
                    "allocation_fraction",
                    "booking_fraction",
                ),
                lot_count=_first(target, "lot_count"),
                quantity=_first(target, "quantity"),
                warnings=tuple(getattr(target, "warnings", ())),
            )
        )
    return tuple(result)


def project_integrated_three_target_trade_plan(
    value: IntegratedThreeTargetTradePlanResultV1,
) -> DashboardTradePlanViewV1:
    if type(value) is not IntegratedThreeTargetTradePlanResultV1:
        raise TypeError(
            "value must be exact IntegratedThreeTargetTradePlanResultV1"
        )

    canonical = value.canonical_trade_plan_input
    opportunity = canonical.trade_opportunity
    entry = value.entry_zone_result
    stop = value.stop_loss_result
    target_result = value.three_target_result
    selection = value.option_contract_selection_result
    capital = value.capital_quantity_result
    selected_candidate = getattr(selection, "selected_contract", None)
    contract = getattr(selected_candidate, "contract", None)

    status = value.status
    plan_status = "READY" if status == "READY" else status
    blockers = tuple(value.blockers)
    warnings = tuple(value.warnings)
    reasons = tuple(value.decision_reasons)

    return DashboardTradePlanViewV1(
        trade_plan_id=capital.trade_plan_id,
        selected_opportunity_id=opportunity.opportunity_id,
        evaluated_at=_first(
            capital,
            "evaluated_at",
        )
        or _first(target_result, "evaluated_at")
        or canonical.evaluated_at,
        underlying_symbol=canonical.underlying_symbol,
        exchange=canonical.exchange,
        market=canonical.underlying_symbol,
        plan_status=plan_status,
        direction=target_result.direction,
        instrument_type="INDEX_OPTION",
        opportunity_confidence=opportunity.opportunity_score,
        option_confidence=_first(selection, "selected_score"),
        plan_confidence=_first(
            value,
            "plan_confidence",
        )
        or opportunity.opportunity_score,
        selected_option_contract_id=_text(
            _first(contract, "contract_id", "instrument_token")
        ),
        selected_option_symbol=_text(
            _first(contract, "trading_symbol", "symbol")
        ),
        strike=_first(contract, "strike"),
        option_type=_text(
            _first(contract, "option_type", "option_right")
        ),
        entry_zone_lower=_first(
            entry,
            "entry_zone_lower",
            "entry_lower",
            "lower_bound",
        ),
        entry_zone_upper=_first(
            entry,
            "entry_zone_upper",
            "entry_upper",
            "upper_bound",
        ),
        entry_reference_price=_first(
            entry,
            "entry_reference_price",
            "reference_price",
        ),
        entry_tolerance_fraction=_first(
            entry,
            "entry_tolerance_fraction",
            "tolerance_fraction",
        ),
        maximum_chase_price=_first(
            entry,
            "maximum_chase_price",
            "max_chase_price",
        ),
        entry_method=_text(_first(entry, "entry_method", "method")),
        stop_loss_price=_first(stop, "stop_loss_price"),
        stop_loss_method=_text(
            _first(stop, "stop_loss_method", "method")
        ),
        stop_distance=_first(stop, "stop_distance"),
        stop_distance_fraction=_first(
            stop,
            "stop_distance_fraction",
        ),
        targets=_targets(target_result),
        lot_size=_first(capital, "lot_size"),
        lot_count=_first(capital, "planned_lot_count"),
        quantity=_first(capital, "planned_quantity"),
        available_capital=_first(capital, "available_capital"),
        required_capital=_first(
            capital,
            "estimated_total_capital_requirement",
            "estimated_premium_outlay",
        ),
        risk_amount=_first(capital, "estimated_risk_amount"),
        maximum_permissible_loss=_first(
            capital,
            "effective_risk_budget",
            "maximum_risk_amount",
        ),
        estimated_entry_cost=_first(
            capital,
            "estimated_brokerage",
        ),
        estimated_exit_cost=None,
        estimated_total_charges=_first(
            capital,
            "estimated_total_trading_cost",
        ),
        estimated_slippage_cost=_first(
            capital,
            "estimated_slippage",
        ),
        expiry=_first(contract, "expiry_date", "expiry"),
        days_to_expiry=_first(contract, "days_to_expiry"),
        expiry_category=_text(
            _first(contract, "expiry_category")
        ),
        invalidation_rules=tuple(
            getattr(stop, "invalidation_rules", ())
        ),
        blockers=blockers,
        warnings=warnings,
        decision_reasons=reasons,
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )
