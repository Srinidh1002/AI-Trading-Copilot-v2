from __future__ import annotations

from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.three_target_trade_plan_v1 import ThreeTargetTradePlanV1
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1

from .dashboard_opportunity_view_v1 import DashboardOpportunityViewV1
from .dashboard_paper_fill_view_v1 import DashboardPaperFillViewV1
from .dashboard_paper_position_detail_view_v1 import (
    DashboardPaperPositionDetailViewV1,
)
from .dashboard_trade_plan_target_view_v1 import (
    DashboardTradePlanTargetViewV1,
)
from .dashboard_trade_plan_view_v1 import DashboardTradePlanViewV1


_PENDING_STATES = frozenset({"PLANNED", "WAITING_FOR_ENTRY"})
_ACTIVE_STATES = frozenset({"OPEN", "PARTIALLY_EXITED"})
_BLOCKED_STATES = frozenset({"BLOCKED"})
_TERMINAL_STATES = frozenset(
    {
        "CLOSED_TARGET_1",
        "CLOSED_TARGET_2",
        "CLOSED_TARGET_3",
        "CLOSED_STOP",
        "CLOSED_INVALIDATED",
        "CLOSED_SESSION",
        "CLOSED_EXPIRY",
        "CANCELLED",
    }
)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _first_attribute(value: object, *names: str) -> object | None:
    if value is None:
        return None
    for name in names:
        candidate = getattr(value, name, None)
        if candidate is not None:
            return candidate
    return None


def _merge_diagnostics(*values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for items in values:
        for item in items:
            if item not in result:
                result.append(item)
    return tuple(result)


def _display_group(lifecycle_state: str) -> str:
    if lifecycle_state in _PENDING_STATES:
        return "PENDING"
    if lifecycle_state in _ACTIVE_STATES:
        return "ACTIVE"
    if lifecycle_state in _BLOCKED_STATES:
        return "BLOCKED"
    if lifecycle_state in _TERMINAL_STATES:
        return "TERMINAL"
    raise ValueError("unsupported P7 lifecycle state")


def project_trade_opportunity(
    value: TradeOpportunityV1,
) -> DashboardOpportunityViewV1:
    if type(value) is not TradeOpportunityV1:
        raise TypeError("value must be exact TradeOpportunityV1")

    return DashboardOpportunityViewV1(
        opportunity_id=value.opportunity_id,
        created_at=value.created_at,
        snapshot_id=value.snapshot_id,
        decision_id=value.decision_id,
        underlying_symbol=value.underlying_symbol,
        exchange=value.exchange,
        opportunity_status=value.opportunity_status,
        action=value.action,
        directional_bias=value.directional_bias,
        option_type=value.option_type,
        contract_id=value.contract_id,
        trading_symbol=value.trading_symbol,
        instrument_token=value.instrument_token,
        strike=value.strike,
        expiry=value.expiry,
        lot_size=value.lot_size,
        reference_option_price=value.reference_option_price,
        technical_strength=value.technical_strength,
        option_chain_strength=value.option_chain_strength,
        contract_ranking_score=value.contract_ranking_score,
        decision_confidence=value.decision_confidence,
        opportunity_score=value.opportunity_score,
        supporting_evidence=tuple(value.supporting_evidence),
        contradictions=tuple(value.contradictions),
        blockers=tuple(value.blockers),
        warnings=tuple(value.warnings),
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )


def _project_target(value: object, expected_number: int) -> DashboardTradePlanTargetViewV1:
    if value is None:
        raise ValueError("READY plan target cannot be None")

    target_number = getattr(value, "target_number", None)
    if target_number != expected_number:
        raise ValueError("target number does not match target position")

    return DashboardTradePlanTargetViewV1(
        target_name=f"T{expected_number}",
        target_price=getattr(value, "target_price"),
        reward_amount=_first_attribute(value, "reward_amount"),
        reward_to_risk=_first_attribute(
            value,
            "reward_to_risk",
            "reward_risk_ratio",
        ),
        booking_fraction=_first_attribute(
            value,
            "allocation_fraction",
            "booking_fraction",
            "quantity_fraction",
        ),
        warnings=tuple(getattr(value, "warnings", ())),
    )


def project_three_target_trade_plan(
    value: ThreeTargetTradePlanV1,
) -> DashboardTradePlanViewV1:
    if type(value) is not ThreeTargetTradePlanV1:
        raise TypeError("value must be exact ThreeTargetTradePlanV1")

    contract = value.selected_option_contract
    targets: tuple[DashboardTradePlanTargetViewV1, ...] = ()
    if value.plan_status == "READY":
        targets = (
            _project_target(value.target_1, 1),
            _project_target(value.target_2, 2),
            _project_target(value.target_3, 3),
        )

    return DashboardTradePlanViewV1(
        trade_plan_id=value.trade_plan_id,
        selected_opportunity_id=value.selected_opportunity_id,
        evaluated_at=value.evaluated_at,
        underlying_symbol=value.underlying_symbol,
        exchange=value.exchange,
        market=value.market,
        plan_status=value.plan_status,
        direction=value.direction,
        instrument_type=value.instrument_type,
        opportunity_confidence=value.opportunity_confidence,
        option_confidence=value.option_confidence,
        plan_confidence=value.plan_confidence,
        selected_option_contract_id=_optional_text(
            _first_attribute(contract, "contract_id", "selected_option_contract_id")
        ),
        selected_option_symbol=_optional_text(
            _first_attribute(contract, "trading_symbol", "option_symbol")
        ),
        strike=_first_attribute(contract, "strike"),
        option_type=_optional_text(_first_attribute(contract, "option_type")),
        entry_zone_lower=value.entry_zone_lower,
        entry_zone_upper=value.entry_zone_upper,
        entry_reference_price=value.entry_reference_price,
        entry_tolerance_fraction=value.entry_tolerance_fraction,
        maximum_chase_price=value.maximum_chase_price,
        entry_method=value.entry_method,
        stop_loss_price=value.stop_loss_price,
        stop_loss_method=value.stop_loss_method,
        stop_distance=value.stop_distance,
        stop_distance_fraction=value.stop_distance_fraction,
        targets=targets,
        lot_size=value.lot_size,
        lot_count=value.lot_count,
        quantity=value.quantity,
        available_capital=value.available_capital,
        required_capital=value.required_capital,
        risk_amount=value.risk_amount,
        maximum_permissible_loss=value.maximum_permissible_loss,
        estimated_entry_cost=value.estimated_entry_cost,
        estimated_exit_cost=value.estimated_exit_cost,
        estimated_total_charges=value.estimated_total_charges,
        estimated_slippage_cost=value.estimated_slippage_cost,
        expiry=value.expiry,
        days_to_expiry=value.days_to_expiry,
        expiry_category=value.expiry_category,
        invalidation_rules=tuple(value.invalidation_rules),
        blockers=tuple(value.blockers),
        warnings=tuple(value.warnings),
        decision_reasons=tuple(value.decision_reasons),
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )


def project_paper_trade_fill(
    value: PaperTradeFillV1,
) -> DashboardPaperFillViewV1:
    if type(value) is not PaperTradeFillV1:
        raise TypeError("value must be exact PaperTradeFillV1")

    return DashboardPaperFillViewV1(
        fill_id=value.fill_id,
        fill_type=value.fill_type,
        fill_reason=value.fill_reason,
        side=value.side,
        filled_lot_count=value.filled_lot_count,
        lot_size=value.lot_size,
        filled_quantity=value.filled_quantity,
        fill_price=value.fill_price,
        gross_notional=value.gross_notional,
        estimated_trading_cost=value.estimated_trading_cost,
        net_cash_effect=value.net_cash_effect,
        filled_at=value.filled_at,
        source=value.source,
        target_name=value.target_name,
        warnings=tuple(value.warnings),
    )


def project_paper_trade_position_detail(
    value: PaperTradePersistenceSnapshotV1,
) -> DashboardPaperPositionDetailViewV1:
    if type(value) is not PaperTradePersistenceSnapshotV1:
        raise TypeError(
            "value must be exact PaperTradePersistenceSnapshotV1"
        )

    lifecycle = value.lifecycle_state
    position = value.position
    pnl = value.pnl_evidence

    fills: tuple[DashboardPaperFillViewV1, ...] = ()
    if position is not None:
        fills = (
            project_paper_trade_fill(position.entry_fill),
            *tuple(project_paper_trade_fill(item) for item in position.exit_fills),
        )

    lifecycle_warnings = tuple(lifecycle.warnings)
    lifecycle_blockers = tuple(lifecycle.blockers)
    lifecycle_reasons = tuple(lifecycle.decision_reasons)

    position_warnings = tuple(position.warnings) if position is not None else ()
    position_blockers = tuple(position.blockers) if position is not None else ()
    position_reasons = (
        tuple(position.decision_reasons) if position is not None else ()
    )
    pnl_warnings = tuple(pnl.warnings) if pnl is not None else ()

    realized_net_pnl = (
        pnl.realized_net_pnl_after
        if pnl is not None
        else position.realized_net_pnl
        if position is not None
        else None
    )
    unrealized_pnl = (
        pnl.unrealized_pnl_after
        if pnl is not None
        else position.unrealized_pnl
        if position is not None
        else None
    )
    total_pnl = (
        pnl.total_pnl_after
        if pnl is not None
        else position.total_pnl
        if position is not None
        else None
    )

    return DashboardPaperPositionDetailViewV1(
        paper_trade_id=value.paper_trade_id,
        position_id=position.position_id if position is not None else None,
        trade_plan_id=lifecycle.trade_plan_id,
        integrated_trade_plan_result_id=(
            lifecycle.integrated_trade_plan_result_id
        ),
        lifecycle_state_id=lifecycle.lifecycle_state_id,
        lifecycle_state=lifecycle.current_state,
        lifecycle_display_group=_display_group(lifecycle.current_state),
        transition_sequence=lifecycle.transition_sequence,
        is_terminal=lifecycle.is_terminal,
        last_transition_code=lifecycle.last_transition_code,
        updated_at=value.updated_at,
        market=position.market if position is not None else None,
        exchange=position.exchange if position is not None else None,
        underlying_symbol=(
            position.underlying_symbol if position is not None else None
        ),
        option_symbol=position.option_symbol if position is not None else None,
        direction=position.direction if position is not None else None,
        option_type=position.option_type if position is not None else None,
        strike=position.strike if position is not None else None,
        expiry=position.expiry if position is not None else None,
        entry_price=position.entry_price if position is not None else None,
        opened_at=position.opened_at if position is not None else None,
        initial_lot_count=(
            position.initial_lot_count if position is not None else None
        ),
        lot_size=position.lot_size if position is not None else None,
        initial_quantity=(
            position.initial_quantity if position is not None else None
        ),
        remaining_lot_count=(
            position.remaining_lot_count if position is not None else None
        ),
        remaining_quantity=(
            position.remaining_quantity if position is not None else None
        ),
        target_1_lot_count=(
            position.target_1_lot_count if position is not None else None
        ),
        target_2_lot_count=(
            position.target_2_lot_count if position is not None else None
        ),
        target_3_lot_count=(
            position.target_3_lot_count if position is not None else None
        ),
        runner_lot_count=(
            position.runner_lot_count if position is not None else None
        ),
        stop_loss=position.stop_loss if position is not None else None,
        target_1=position.target_1 if position is not None else None,
        target_2=position.target_2 if position is not None else None,
        target_3=position.target_3 if position is not None else None,
        estimated_premium_outlay=(
            position.estimated_premium_outlay
            if position is not None
            else None
        ),
        estimated_risk_amount=(
            position.estimated_risk_amount
            if position is not None
            else None
        ),
        estimated_total_trading_cost=(
            position.estimated_total_trading_cost
            if position is not None
            else None
        ),
        estimated_total_capital_requirement=(
            position.estimated_total_capital_requirement
            if position is not None
            else None
        ),
        realized_net_pnl=realized_net_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        current_option_price=(
            pnl.current_option_price if pnl is not None else None
        ),
        pnl_calculated_at=pnl.calculated_at if pnl is not None else None,
        fills=fills,
        terminal_reason=lifecycle.terminal_reason,
        terminal_target=lifecycle.terminal_target,
        blockers=_merge_diagnostics(
            lifecycle_blockers,
            position_blockers,
        ),
        warnings=_merge_diagnostics(
            lifecycle_warnings,
            position_warnings,
            pnl_warnings,
        ),
        decision_reasons=_merge_diagnostics(
            lifecycle_reasons,
            position_reasons,
        ),
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )
