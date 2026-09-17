"""Task 5 quantity sizing and executable PAPER plan assembly."""
from __future__ import annotations

from datetime import datetime
from math import floor, isfinite

from services.contracts.executable_paper_trade_plan_result_v1 import (
    ExecutablePaperTradePlanResultV1,
)
from services.contracts.selected_option_affordability_risk_result_v1 import (
    SelectedOptionAffordabilityRiskResultV1,
)
from services.contracts.selected_option_entry_stop_target_plan_result_v1 import (
    SelectedOptionEntryStopTargetPlanResultV1,
)
from services.trade_planning.capital_quantity_planner import (
    _allocate_target_lots,
)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _number(value: object, name: str, *, maximum: float | None = None) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0.0
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(name)
    return float(value)


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise ValueError(name)
    return value


def _weights(value: object) -> tuple[float, float, float]:
    if not isinstance(value, tuple) or len(value) != 3:
        raise ValueError("target_allocation_weights")
    result = tuple(_number(item, "target_allocation_weights") for item in value)
    if sum(result) <= 0.0:
        raise ValueError("target_allocation_weights")
    return result


def _unavailable(
    *,
    executable_plan_id: str,
    affordability: SelectedOptionAffordabilityRiskResultV1,
    task4: SelectedOptionEntryStopTargetPlanResultV1,
    evaluated_at: datetime,
    blockers: tuple[str, ...],
) -> ExecutablePaperTradePlanResultV1:
    return ExecutablePaperTradePlanResultV1(
        executable_plan_id=executable_plan_id,
        task4_planning_result_id=task4.planning_result_id,
        affordability_result_id=affordability.affordability_result_id,
        certification_result_id=affordability.certification_result_id,
        parent_cycle_id=affordability.parent_cycle_id,
        parent_decision_id=affordability.parent_decision_id,
        bridge_result_id=affordability.bridge_result_id,
        candidate_id=affordability.candidate_id,
        observation_id=affordability.observation_id,
        ranking_result_id=affordability.ranking_result_id,
        contract_id=None,
        selected_market=None,
        direction=None,
        option_right=None,
        trading_symbol=None,
        instrument_token=None,
        expiry_date=None,
        strike=None,
        evaluated_at=evaluated_at,
        status="UNAVAILABLE",
        executable=False,
        entry_result=None,
        stop_loss_result=None,
        target_result=None,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(affordability.warnings + task4.warnings)),
    )


def assemble_executable_paper_trade_plan(
    *,
    executable_plan_id: str,
    affordability: SelectedOptionAffordabilityRiskResultV1,
    task4: SelectedOptionEntryStopTargetPlanResultV1,
    evaluated_at: datetime,
    minimum_lot_count: int = 1,
    maximum_lot_count: int = 1,
    estimated_costs_per_lot: float = 0.0,
    target_allocation_enabled: bool = True,
    target_allocation_weights: tuple[float, float, float] = (0.3, 0.4, 0.3),
    reserve_runner_lots: int = 0,
) -> ExecutablePaperTradePlanResultV1:
    """Size one certified option plan without execution or persistence."""

    if type(affordability) is not SelectedOptionAffordabilityRiskResultV1:
        raise TypeError("affordability")
    if type(task4) is not SelectedOptionEntryStopTargetPlanResultV1:
        raise TypeError("task4")

    plan_id = _text(executable_plan_id, "executable_plan_id")
    now = _aware(evaluated_at, "evaluated_at")
    minimum_lots = _positive_int(minimum_lot_count, "minimum_lot_count")
    maximum_lots = _positive_int(maximum_lot_count, "maximum_lot_count")
    if maximum_lots < minimum_lots:
        raise ValueError("lot bounds")
    costs_per_lot = _number(estimated_costs_per_lot, "estimated_costs_per_lot")
    if type(target_allocation_enabled) is not bool:
        raise TypeError("target_allocation_enabled")
    weights = _weights(target_allocation_weights)
    if (
        type(reserve_runner_lots) is not int
        or isinstance(reserve_runner_lots, bool)
        or reserve_runner_lots < 0
    ):
        raise ValueError("reserve_runner_lots")

    if (
        affordability.status != "READY"
        or not affordability.planning_allowed
        or task4.status != "READY"
        or not task4.planning_allowed
    ):
        return _unavailable(
            executable_plan_id=plan_id,
            affordability=affordability,
            task4=task4,
            evaluated_at=now,
            blockers=tuple(
                dict.fromkeys(
                    ("TASK5_UPSTREAM_NOT_READY",)
                    + affordability.blockers
                    + task4.blockers
                )
            ),
        )

    coherence_blockers: list[str] = []
    if task4.affordability_result_id != affordability.affordability_result_id:
        coherence_blockers.append("TASK5_AFFORDABILITY_ID_MISMATCH")
    if task4.certification_result_id != affordability.certification_result_id:
        coherence_blockers.append("TASK5_CERTIFICATION_ID_MISMATCH")
    if task4.contract_id != affordability.contract_id:
        coherence_blockers.append("TASK5_CONTRACT_ID_MISMATCH")

    entry = task4.entry_result
    stop = task4.stop_loss_result
    targets = task4.target_result

    if stop.stop_reference_price != entry.entry_reference_price:
        coherence_blockers.append("TASK5_ENTRY_STOP_REFERENCE_MISMATCH")
    if targets.entry_reference_price != entry.entry_reference_price:
        coherence_blockers.append("TASK5_ENTRY_TARGET_REFERENCE_MISMATCH")
    if targets.stop_loss_price != stop.stop_loss_price:
        coherence_blockers.append("TASK5_STOP_TARGET_REFERENCE_MISMATCH")

    if coherence_blockers:
        return ExecutablePaperTradePlanResultV1(
            executable_plan_id=plan_id,
            task4_planning_result_id=task4.planning_result_id,
            affordability_result_id=affordability.affordability_result_id,
            certification_result_id=affordability.certification_result_id,
            parent_cycle_id=affordability.parent_cycle_id,
            parent_decision_id=affordability.parent_decision_id,
            bridge_result_id=affordability.bridge_result_id,
            candidate_id=affordability.candidate_id,
            observation_id=affordability.observation_id,
            ranking_result_id=affordability.ranking_result_id,
            contract_id=affordability.contract_id,
            selected_market=affordability.selected_market,
            direction=affordability.direction,
            option_right=affordability.option_right,
            trading_symbol=affordability.trading_symbol,
            instrument_token=affordability.instrument_token,
            expiry_date=affordability.expiry_date,
            strike=affordability.strike,
            evaluated_at=now,
            status="BLOCKED",
            executable=False,
            entry_result=entry,
            stop_loss_result=stop,
            target_result=targets,
            blockers=tuple(coherence_blockers),
            warnings=tuple(dict.fromkeys(affordability.warnings + task4.warnings)),
        )

    risk_per_unit = stop.stop_distance
    risk_per_lot = risk_per_unit * affordability.lot_size + costs_per_lot
    risk_based_lot_limit = floor(affordability.maximum_new_loss / risk_per_lot)
    policy_lot_limit = maximum_lots
    planned_lots = min(
        affordability.maximum_affordable_lots,
        risk_based_lot_limit,
        policy_lot_limit,
    )

    blockers: list[str] = []
    if risk_based_lot_limit < 1:
        blockers.append("RISK_INSUFFICIENT_FOR_ONE_LOT")
    if planned_lots < minimum_lots:
        blockers.append("MINIMUM_LOT_COUNT_NOT_MET")
    if reserve_runner_lots > planned_lots:
        blockers.append("RUNNER_LOTS_EXCEED_PLAN")

    if blockers:
        return ExecutablePaperTradePlanResultV1(
            executable_plan_id=plan_id,
            task4_planning_result_id=task4.planning_result_id,
            affordability_result_id=affordability.affordability_result_id,
            certification_result_id=affordability.certification_result_id,
            parent_cycle_id=affordability.parent_cycle_id,
            parent_decision_id=affordability.parent_decision_id,
            bridge_result_id=affordability.bridge_result_id,
            candidate_id=affordability.candidate_id,
            observation_id=affordability.observation_id,
            ranking_result_id=affordability.ranking_result_id,
            contract_id=affordability.contract_id,
            selected_market=affordability.selected_market,
            direction=affordability.direction,
            option_right=affordability.option_right,
            trading_symbol=affordability.trading_symbol,
            instrument_token=affordability.instrument_token,
            expiry_date=affordability.expiry_date,
            strike=affordability.strike,
            evaluated_at=now,
            status="BLOCKED",
            executable=False,
            entry_result=entry,
            stop_loss_result=stop,
            target_result=targets,
            lot_size=affordability.lot_size,
            maximum_authorized_loss=affordability.maximum_new_loss,
            estimated_costs_per_lot=costs_per_lot,
            maximum_affordable_lots=affordability.maximum_affordable_lots,
            risk_based_lot_limit=risk_based_lot_limit,
            policy_lot_limit=policy_lot_limit,
            blockers=tuple(blockers),
            warnings=tuple(dict.fromkeys(affordability.warnings + task4.warnings)),
        )

    allocatable_lots = planned_lots - reserve_runner_lots
    if target_allocation_enabled:
        allocated, _, _, _, _ = _allocate_target_lots(
            allocatable_lots,
            weights,
        )
        target_1_lots, target_2_lots, target_3_lots = allocated
    else:
        target_1_lots = 0
        target_2_lots = 0
        target_3_lots = 0
        reserve_runner_lots = planned_lots

    planned_quantity = planned_lots * affordability.lot_size
    entry_premium = entry.entry_reference_price
    premium_outlay = entry_premium * planned_quantity
    total_costs = costs_per_lot * planned_lots
    total_capital = premium_outlay + total_costs
    maximum_loss = risk_per_lot * planned_lots

    if total_capital > affordability.deployable_capital + 1e-9:
        return ExecutablePaperTradePlanResultV1(
            executable_plan_id=plan_id,
            task4_planning_result_id=task4.planning_result_id,
            affordability_result_id=affordability.affordability_result_id,
            certification_result_id=affordability.certification_result_id,
            parent_cycle_id=affordability.parent_cycle_id,
            parent_decision_id=affordability.parent_decision_id,
            bridge_result_id=affordability.bridge_result_id,
            candidate_id=affordability.candidate_id,
            observation_id=affordability.observation_id,
            ranking_result_id=affordability.ranking_result_id,
            contract_id=affordability.contract_id,
            selected_market=affordability.selected_market,
            direction=affordability.direction,
            option_right=affordability.option_right,
            trading_symbol=affordability.trading_symbol,
            instrument_token=affordability.instrument_token,
            expiry_date=affordability.expiry_date,
            strike=affordability.strike,
            evaluated_at=now,
            status="BLOCKED",
            executable=False,
            entry_result=entry,
            stop_loss_result=stop,
            target_result=targets,
            lot_size=affordability.lot_size,
            maximum_authorized_loss=affordability.maximum_new_loss,
            estimated_costs_per_lot=costs_per_lot,
            maximum_affordable_lots=affordability.maximum_affordable_lots,
            risk_based_lot_limit=risk_based_lot_limit,
            policy_lot_limit=policy_lot_limit,
            blockers=("PLANNED_CAPITAL_EXCEEDS_DEPLOYABLE_CAPITAL",),
            warnings=tuple(dict.fromkeys(affordability.warnings + task4.warnings)),
        )

    return ExecutablePaperTradePlanResultV1(
        executable_plan_id=plan_id,
        task4_planning_result_id=task4.planning_result_id,
        affordability_result_id=affordability.affordability_result_id,
        certification_result_id=affordability.certification_result_id,
        parent_cycle_id=affordability.parent_cycle_id,
        parent_decision_id=affordability.parent_decision_id,
        bridge_result_id=affordability.bridge_result_id,
        candidate_id=affordability.candidate_id,
        observation_id=affordability.observation_id,
        ranking_result_id=affordability.ranking_result_id,
        contract_id=affordability.contract_id,
        selected_market=affordability.selected_market,
        direction=affordability.direction,
        option_right=affordability.option_right,
        trading_symbol=affordability.trading_symbol,
        instrument_token=affordability.instrument_token,
        expiry_date=affordability.expiry_date,
        strike=affordability.strike,
        evaluated_at=now,
        status="READY",
        executable=True,
        entry_result=entry,
        stop_loss_result=stop,
        target_result=targets,
        lot_size=affordability.lot_size,
        planned_lot_count=planned_lots,
        planned_quantity=planned_quantity,
        risk_per_unit=risk_per_unit,
        risk_per_lot=risk_per_lot,
        maximum_authorized_loss=affordability.maximum_new_loss,
        estimated_entry_premium=entry_premium,
        estimated_premium_outlay=premium_outlay,
        estimated_costs_per_lot=costs_per_lot,
        estimated_total_costs=total_costs,
        estimated_total_capital_requirement=total_capital,
        estimated_maximum_loss=maximum_loss,
        maximum_affordable_lots=affordability.maximum_affordable_lots,
        risk_based_lot_limit=risk_based_lot_limit,
        policy_lot_limit=policy_lot_limit,
        target_1_lot_count=target_1_lots,
        target_2_lot_count=target_2_lots,
        target_3_lot_count=target_3_lots,
        runner_lot_count=reserve_runner_lots,
        blockers=(),
        warnings=tuple(dict.fromkeys(affordability.warnings + task4.warnings)),
    )
