"""Project certified planning outputs into one final recommendation."""
from __future__ import annotations

from services.contracts.capital_risk_authority_v1 import (
    CapitalRiskAuthorityResultV1,
)
from services.contracts.final_trade_recommendation_v1 import (
    FinalTradeRecommendationV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)


def _blocked_projection(
    *,
    recommendation_id: str,
    bridge: SelectedMarketPlanningBridgeResultV1,
    authority: CapitalRiskAuthorityResultV1,
    planning: IntegratedThreeTargetTradePlanResultV1,
    action: str,
    blockers: tuple[str, ...],
) -> FinalTradeRecommendationV1:
    return FinalTradeRecommendationV1(
        recommendation_id=recommendation_id,
        parent_cycle_id=bridge.parent_cycle_id,
        evaluated_at=max(
            bridge.evaluated_at,
            authority.evaluated_at,
        ),
        action=action,
        selected_market=(
            None if action == "NO_TRADE" else bridge.selected_market
        ),
        expiry=None,
        strike=None,
        contract=None,
        entry_zone_lower=None,
        entry_zone_upper=None,
        stop_loss=None,
        target_1=None,
        target_2=None,
        target_3=None,
        lots=0,
        quantity=0,
        capital_required=0.0,
        maximum_loss=0.0,
        risk_reward=None,
        confidence=(
            None
            if bridge.selected_candidate is None
            else bridge.selected_candidate.confidence
        ),
        losing_market=bridge.losing_market,
        losing_outcome_reason=bridge.losing_outcome_reason,
        reasons=tuple(
            dict.fromkeys(
                bridge.reasons
                + tuple(planning.decision_reasons)
            )
        ),
        invalidation_conditions=bridge.invalidation_conditions,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(
            dict.fromkeys(
                bridge.warnings
                + authority.warnings
                + tuple(planning.warnings)
            )
        ),
    )


def project_final_trade_recommendation(
    *,
    recommendation_id: str,
    bridge: SelectedMarketPlanningBridgeResultV1,
    authority: CapitalRiskAuthorityResultV1,
    planning: IntegratedThreeTargetTradePlanResultV1,
) -> FinalTradeRecommendationV1:
    """Return CALL/PUT only when every upstream authority is READY."""

    if type(bridge) is not SelectedMarketPlanningBridgeResultV1:
        raise TypeError("bridge")
    if type(authority) is not CapitalRiskAuthorityResultV1:
        raise TypeError("authority")
    if type(planning) is not IntegratedThreeTargetTradePlanResultV1:
        raise TypeError("planning")

    if bridge.action == "NO_TRADE":
        return _blocked_projection(
            recommendation_id=recommendation_id,
            bridge=bridge,
            authority=authority,
            planning=planning,
            action="NO_TRADE",
            blockers=bridge.blockers or ("NO_ELIGIBLE_MARKET",),
        )

    if bridge.selected_market != authority.selected_market:
        raise ValueError("bridge/authority market mismatch")

    upstream_blockers = tuple(
        dict.fromkeys(
            bridge.blockers
            + authority.blockers
            + tuple(planning.blockers)
        )
    )
    if (
        bridge.action == "WAIT"
        or not bridge.planning_allowed
        or authority.status != "READY"
        or not authority.planning_allowed
        or planning.status != "READY"
    ):
        return _blocked_projection(
            recommendation_id=recommendation_id,
            bridge=bridge,
            authority=authority,
            planning=planning,
            action="WAIT",
            blockers=upstream_blockers
            or ("PLANNING_NOT_READY",),
        )

    entry = planning.entry_zone_result
    stop = planning.stop_loss_result
    targets = planning.three_target_result
    option = planning.option_contract_selection_result
    size = planning.capital_quantity_result

    identity = bridge.selected_market
    for result in (entry, stop, targets, option):
        if (
            result.underlying_symbol,
            result.exchange,
        ) != identity:
            raise ValueError("planning market identity mismatch")
    if entry.option_right != bridge.action:
        raise ValueError("bridge/planning action mismatch")
    if option.option_right != bridge.action:
        raise ValueError("option right mismatch")

    if any(
        result.status != "READY"
        for result in (entry, stop, targets, option, size)
    ):
        raise ValueError("READY integration contains non-ready child")

    capital_required = (
        size.estimated_total_capital_requirement
        if size.estimated_total_capital_requirement is not None
        else size.estimated_premium_outlay
    )
    maximum_loss = size.estimated_risk_amount
    if capital_required is None or maximum_loss is None:
        raise ValueError("capital and maximum loss must be known")
    if capital_required > authority.deployable_capital + 1e-9:
        raise ValueError("planned capital exceeds deployable capital")
    if maximum_loss > authority.maximum_new_loss + 1e-9:
        raise ValueError("planned loss exceeds authority")
    if size.planned_lot_count > authority.maximum_affordable_lots:
        raise ValueError("planned lots exceed authority")

    target_1 = targets.target_1
    target_2 = targets.target_2
    target_3 = targets.target_3

    return FinalTradeRecommendationV1(
        recommendation_id=recommendation_id,
        parent_cycle_id=bridge.parent_cycle_id,
        evaluated_at=max(
            bridge.evaluated_at,
            authority.evaluated_at,
            entry.evaluated_at,
            stop.evaluated_at,
            targets.evaluated_at,
            option.evaluated_at,
            size.evaluated_at,
        ),
        action=bridge.action,
        selected_market=identity,
        expiry=option.selected_expiry,
        strike=option.selected_strike,
        contract=option.selected_trading_symbol,
        entry_zone_lower=entry.entry_zone_lower,
        entry_zone_upper=entry.entry_zone_upper,
        stop_loss=stop.stop_loss_price,
        target_1=target_1.target_price,
        target_2=target_2.target_price,
        target_3=target_3.target_price,
        lots=size.planned_lot_count,
        quantity=size.planned_quantity,
        capital_required=capital_required,
        maximum_loss=maximum_loss,
        risk_reward=targets.weighted_reward_to_risk,
        confidence=bridge.selected_candidate.confidence,
        losing_market=bridge.losing_market,
        losing_outcome_reason=bridge.losing_outcome_reason,
        reasons=tuple(
            dict.fromkeys(
                bridge.reasons
                + tuple(planning.decision_reasons)
                + tuple(entry.decision_reasons)
                + tuple(stop.decision_reasons)
                + tuple(targets.decision_reasons)
                + tuple(option.decision_reasons)
            )
        ),
        invalidation_conditions=tuple(
            dict.fromkeys(
                bridge.invalidation_conditions
                + tuple(stop.invalidation_rules)
            )
        ),
        warnings=tuple(
            dict.fromkeys(
                bridge.warnings
                + authority.warnings
                + tuple(planning.warnings)
                + tuple(entry.warnings)
                + tuple(stop.warnings)
                + tuple(targets.warnings)
                + tuple(option.warnings)
                + tuple(size.warnings)
            )
        ),
    )
