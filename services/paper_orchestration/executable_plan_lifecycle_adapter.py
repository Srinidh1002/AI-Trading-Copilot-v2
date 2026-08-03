"""Task 6 compatibility handoff into the existing PAPER lifecycle."""
from __future__ import annotations

from types import SimpleNamespace

from services.contracts.capital_quantity_planning_result_v1 import (
    CapitalQuantityPlanningResultV1,
)
from services.contracts.executable_paper_trade_plan_result_v1 import (
    ExecutablePaperTradePlanResultV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_selection_result_v1 import (
    OptionContractSelectionResultV1,
)
from services.contracts.option_contract_v1 import OptionContractV1


def adapt_executable_plan_to_paper_lifecycle(
    value: ExecutablePaperTradePlanResultV1,
) -> IntegratedThreeTargetTradePlanResultV1:
    """Copy a READY Task 5 plan into the exact legacy PAPER handoff shape."""

    if type(value) is not ExecutablePaperTradePlanResultV1:
        raise TypeError("value")
    if value.status != "READY" or not value.executable:
        raise ValueError("executable plan must be READY")
    if (
        value.execution_mode != "PAPER"
        or value.live_execution_eligible is not False
        or value.broker_order_submission is not False
    ):
        raise ValueError("executable plan must remain PAPER-only")

    symbol, exchange = value.selected_market

    contract = OptionContractV1(
        contract_id=value.contract_id,
        underlying_symbol=symbol,
        exchange=exchange,
        trading_symbol=value.trading_symbol,
        option_type=value.option_right,
        strike=value.strike,
        expiry_date=value.expiry_date,
        lot_size=value.lot_size,
        market_timestamp=value.evaluated_at,
        instrument_token=value.instrument_token,
        last_price=value.estimated_entry_premium,
        bid_price=value.estimated_entry_premium,
        ask_price=value.estimated_entry_premium,
        metadata={
            "source": "TASK5_EXECUTABLE_PLAN",
            "executable_plan_id": value.executable_plan_id,
            "certification_result_id": value.certification_result_id,
        },
    )
    candidate = OptionContractCandidateV1(
        contract=contract,
        candidate_status="ELIGIBLE",
        moneyness="UNKNOWN",
        strike_distance_percent=0.0,
        spread_percent=0.0,
        liquidity_score=1.0,
        proximity_score=1.0,
        open_interest_score=1.0,
        volume_score=1.0,
        spread_score=1.0,
        implied_volatility_score=1.0,
        intelligence_alignment_score=1.0,
        total_score=1.0,
    )
    selection_result_id = f"{value.executable_plan_id}:selection"
    selection = OptionContractSelectionResultV1(
        selection_result_id=selection_result_id,
        selection_id=f"{value.executable_plan_id}:selection-input",
        evaluated_at=value.evaluated_at,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=value.direction,
        option_right=value.option_right,
        status="READY",
        selected_contract=candidate,
        selected_rank=1,
        selected_score=1.0,
        selected_reason_codes=("TASK5_CERTIFIED_CONTRACT",),
        premium_affordable=True,
        spread_acceptable=True,
        liquidity_acceptable=True,
        open_interest_acceptable=True,
        volume_acceptable=True,
        moneyness_acceptable=True,
        expiry_acceptable=True,
        lot_size_acceptable=True,
        session_acceptable=True,
        event_acceptable=True,
        effective_maximum_entry_premium=value.estimated_entry_premium,
        effective_maximum_spread_fraction=0.0,
        estimated_one_lot_premium_cost=(
            value.estimated_entry_premium * value.lot_size
        ),
        affordable_lot_count=value.maximum_affordable_lots,
        decision_reasons=("TASK5_EXECUTABLE_PLAN_ADAPTED",),
        warnings=value.warnings,
        metadata={
            "executable_plan_id": value.executable_plan_id,
            "task4_planning_result_id": value.task4_planning_result_id,
        },
    )

    capital = CapitalQuantityPlanningResultV1(
        planning_result_id=f"{value.executable_plan_id}:capital",
        planning_input_id=f"{value.executable_plan_id}:capital-input",
        trade_plan_id=value.executable_plan_id,
        policy_id=f"{value.executable_plan_id}:quantity-policy",
        option_selection_result_id=selection_result_id,
        status="READY",
        available_capital=value.estimated_total_capital_requirement,
        maximum_capital_utilization_fraction=1.0,
        minimum_reserve_capital=0.0,
        deployable_capital=value.estimated_total_capital_requirement,
        reserved_capital=0.0,
        risk_model="CALLER_SUPPLIED_PER_LOT_RISK",
        maximum_risk_amount=value.maximum_authorized_loss,
        effective_risk_budget=value.maximum_authorized_loss,
        per_lot_risk_amount=value.risk_per_lot,
        risk_based_lot_limit=value.risk_based_lot_limit,
        estimated_one_lot_premium_cost=(
            value.estimated_entry_premium * value.lot_size
        ),
        upstream_affordable_lot_limit=value.maximum_affordable_lots,
        deployable_capital_affordable_lot_limit=value.maximum_affordable_lots,
        planned_lot_count=value.planned_lot_count,
        lot_size=value.lot_size,
        planned_quantity=value.planned_quantity,
        estimated_premium_outlay=value.estimated_premium_outlay,
        estimated_risk_amount=value.estimated_maximum_loss,
        target_allocation_enabled=True,
        target_1_lot_count=value.target_1_lot_count,
        target_2_lot_count=value.target_2_lot_count,
        target_3_lot_count=value.target_3_lot_count,
        runner_lot_count=value.runner_lot_count,
        evaluated_at=value.evaluated_at,
        warnings=value.warnings,
        metadata={
            "source": "TASK5_EXECUTABLE_PLAN",
            "executable_plan_id": value.executable_plan_id,
        },
        trading_cost_calculation_mode="TASK5_CALLER_ASSUMPTION",
        estimated_total_trading_cost=value.estimated_total_costs,
        estimated_total_capital_requirement=(
            value.estimated_total_capital_requirement
        ),
        cost_adjusted_capital_feasible=True,
    )

    canonical = SimpleNamespace(
        underlying_symbol=symbol,
        exchange=exchange,
        direction=value.direction,
        trade_opportunity=SimpleNamespace(
            opportunity_id=value.candidate_id or value.executable_plan_id,
            opportunity_score=1.0,
        ),
    )

    return IntegratedThreeTargetTradePlanResultV1(
        integration_id=value.executable_plan_id,
        status="READY",
        canonical_trade_plan_input=canonical,
        entry_zone_result=value.entry_result,
        stop_loss_result=value.stop_loss_result,
        three_target_result=value.target_result,
        option_contract_selection_result=selection,
        capital_quantity_result=capital,
        decision_reasons=("TASK5_EXECUTABLE_PLAN_ADAPTED",),
        warnings=value.warnings,
        metadata={
            "source_schema": value.SCHEMA_VERSION,
            "task4_planning_result_id": value.task4_planning_result_id,
            "affordability_result_id": value.affordability_result_id,
            "certification_result_id": value.certification_result_id,
            "parent_cycle_id": value.parent_cycle_id,
            "parent_decision_id": value.parent_decision_id,
            "bridge_result_id": value.bridge_result_id,
            "candidate_id": value.candidate_id,
            "observation_id": value.observation_id,
            "ranking_result_id": value.ranking_result_id,
        },
    )
