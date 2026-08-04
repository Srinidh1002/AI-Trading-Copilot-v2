"""Task 4 deterministic entry, stop-loss, and target integration."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

from services.contracts.canonical_trade_plan_input_v1 import (
    CanonicalTradePlanInputV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
)
from services.contracts.selected_option_affordability_risk_result_v1 import (
    SelectedOptionAffordabilityRiskResultV1,
)
from services.contracts.selected_option_entry_stop_target_plan_result_v1 import (
    SelectedOptionEntryStopTargetPlanResultV1,
)
from services.contracts.stop_loss_evaluation_input_v1 import (
    StopLossEvaluationInputV1,
)
from services.contracts.three_target_evaluation_input_v1 import (
    ThreeTargetEvaluationInputV1,
)
from services.contracts.trade_planning_policy_v1 import (
    TradePlanningPolicyV1,
)
from services.trade_planning.entry_zone_evaluator import evaluate_entry_zone
from services.trade_planning.stop_loss_evaluator import evaluate_stop_loss
from services.trade_planning.three_target_evaluator import (
    evaluate_three_targets,
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


def _optional_positive(value: object, name: str) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


def _levels(value: object, name: str) -> tuple[float, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    result = tuple(_optional_positive(item, name) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(name)
    return result


def _blocked_result(
    *,
    planning_result_id: str,
    affordability: SelectedOptionAffordabilityRiskResultV1,
    evaluated_at: datetime,
    status: str,
    blockers: tuple[str, ...],
    entry_result=None,
    stop_loss_result=None,
    target_result=None,
    trade_plan_input_id: str | None = None,
    policy_id: str | None = None,
    warnings: tuple[str, ...] = (),
) -> SelectedOptionEntryStopTargetPlanResultV1:
    return SelectedOptionEntryStopTargetPlanResultV1(
        planning_result_id=planning_result_id,
        affordability_result_id=affordability.affordability_result_id,
        certification_result_id=affordability.certification_result_id,
        parent_cycle_id=affordability.parent_cycle_id,
        parent_decision_id=affordability.parent_decision_id,
        bridge_result_id=affordability.bridge_result_id,
        candidate_id=affordability.candidate_id,
        observation_id=affordability.observation_id,
        ranking_result_id=affordability.ranking_result_id,
        contract_id=affordability.contract_id,
        trade_plan_input_id=trade_plan_input_id,
        policy_id=policy_id,
        evaluated_at=evaluated_at,
        status=status,
        planning_allowed=False,
        entry_result=entry_result,
        stop_loss_result=stop_loss_result,
        target_result=target_result,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def plan_selected_option_entry_stop_targets(
    *,
    planning_result_id: str,
    entry_evaluation_id: str,
    entry_evaluation_result_id: str,
    stop_evaluation_id: str,
    stop_evaluation_result_id: str,
    target_evaluation_id: str,
    target_evaluation_result_id: str,
    affordability: SelectedOptionAffordabilityRiskResultV1,
    trade_plan_input: CanonicalTradePlanInputV1,
    policy: TradePlanningPolicyV1,
    evaluated_at: datetime,
    signal_reference_price: float | None = None,
    atr_value: float | None = None,
    structure_stop_price: float | None = None,
    recent_swing_low: float | None = None,
    recent_swing_high: float | None = None,
    expected_move_value: float | None = None,
    structure_target_1: float | None = None,
    structure_target_2: float | None = None,
    structure_target_3: float | None = None,
    resistance_levels: tuple[float, ...] = (),
    support_levels: tuple[float, ...] = (),
) -> SelectedOptionEntryStopTargetPlanResultV1:
    """Use existing pure evaluators without providers, execution, or persistence."""

    if type(affordability) is not SelectedOptionAffordabilityRiskResultV1:
        raise TypeError("affordability")
    if type(trade_plan_input) is not CanonicalTradePlanInputV1:
        raise TypeError("trade_plan_input")
    if type(policy) is not TradePlanningPolicyV1:
        raise TypeError("policy")

    result_id = _text(planning_result_id, "planning_result_id")
    entry_id = _text(entry_evaluation_id, "entry_evaluation_id")
    entry_result_id = _text(
        entry_evaluation_result_id,
        "entry_evaluation_result_id",
    )
    stop_id = _text(stop_evaluation_id, "stop_evaluation_id")
    stop_result_id = _text(
        stop_evaluation_result_id,
        "stop_evaluation_result_id",
    )
    target_id = _text(target_evaluation_id, "target_evaluation_id")
    target_result_id = _text(
        target_evaluation_result_id,
        "target_evaluation_result_id",
    )
    now = _aware(evaluated_at, "evaluated_at")

    signal = _optional_positive(
        signal_reference_price,
        "signal_reference_price",
    )
    atr = _optional_positive(atr_value, "atr_value")
    structure_stop = _optional_positive(
        structure_stop_price,
        "structure_stop_price",
    )
    swing_low = _optional_positive(recent_swing_low, "recent_swing_low")
    swing_high = _optional_positive(recent_swing_high, "recent_swing_high")
    expected_move = _optional_positive(
        expected_move_value,
        "expected_move_value",
    )
    structure_targets = tuple(
        _optional_positive(value, name)
        for value, name in (
            (structure_target_1, "structure_target_1"),
            (structure_target_2, "structure_target_2"),
            (structure_target_3, "structure_target_3"),
        )
    )
    resistance = _levels(resistance_levels, "resistance_levels")
    support = _levels(support_levels, "support_levels")

    if affordability.status != "READY" or not affordability.planning_allowed:
        return _blocked_result(
            planning_result_id=result_id,
            affordability=affordability,
            evaluated_at=now,
            status="UNAVAILABLE",
            blockers=tuple(
                dict.fromkeys(
                    ("AFFORDABILITY_RISK_NOT_READY",)
                    + affordability.blockers
                )
            ),
            warnings=affordability.warnings,
        )

    coherence_blockers: list[str] = []
    identity = (
        trade_plan_input.underlying_symbol,
        trade_plan_input.exchange,
    )
    if identity != affordability.selected_market:
        coherence_blockers.append("TASK4_MARKET_IDENTITY_MISMATCH")
    if trade_plan_input.trade_plan_input_id.strip() == "":
        coherence_blockers.append("TASK4_TRADE_PLAN_ID_UNAVAILABLE")
    if trade_plan_input.available_capital != affordability.total_capital:
        coherence_blockers.append("TASK4_CAPITAL_EVIDENCE_MISMATCH")
    if not trade_plan_input.planning_allowed:
        coherence_blockers.append("TASK4_CANONICAL_PLAN_NOT_ALLOWED")

    option_mid = (
        (affordability.bid_price + affordability.ask_price) / 2.0
    )
    entry_input = EntryZoneEvaluationInputV1(
        evaluation_id=entry_id,
        evaluation_result_id=entry_result_id,
        evaluated_at=now,
        underlying_symbol=identity[0],
        exchange=identity[1],
        trade_plan_input_id=trade_plan_input.trade_plan_input_id,
        policy_id=policy.policy_id,
        direction=affordability.direction,
        option_right=affordability.option_right,
        entry_reference_method=policy.entry_reference_method,
        last_traded_price=affordability.premium,
        bid_price=affordability.bid_price,
        ask_price=affordability.ask_price,
        signal_reference_price=signal,
        option_mid_price=option_mid,
        option_quote_timestamp=affordability.evaluated_at,
        maximum_entry_premium=trade_plan_input.maximum_entry_premium,
        maximum_spread_fraction=trade_plan_input.maximum_spread_fraction,
        planning_allowed=not coherence_blockers,
        blockers=tuple(coherence_blockers),
        warnings=affordability.warnings,
        source_timestamps={"affordability": affordability.evaluated_at},
        metadata={
            "affordability_result_id": affordability.affordability_result_id,
            "contract_id": affordability.contract_id,
        },
    )
    entry_result = evaluate_entry_zone(entry_input, policy)

    if entry_result.status != "READY":
        return _blocked_result(
            planning_result_id=result_id,
            affordability=affordability,
            evaluated_at=now,
            status="BLOCKED",
            blockers=entry_result.blockers,
            entry_result=entry_result,
            trade_plan_input_id=trade_plan_input.trade_plan_input_id,
            policy_id=policy.policy_id,
            warnings=entry_result.warnings,
        )

    stop_input = StopLossEvaluationInputV1(
        evaluation_id=stop_id,
        evaluation_result_id=stop_result_id,
        evaluated_at=now,
        trade_plan_input_id=trade_plan_input.trade_plan_input_id,
        policy_id=policy.policy_id,
        entry_evaluation_result_id=entry_result.evaluation_result_id,
        underlying_symbol=identity[0],
        exchange=identity[1],
        direction=affordability.direction,
        option_right=affordability.option_right,
        entry_reference_price=entry_result.entry_reference_price,
        entry_zone_lower=entry_result.entry_zone_lower,
        entry_zone_upper=entry_result.entry_zone_upper,
        atr_value=atr,
        structure_stop_price=structure_stop,
        premium_reference_price=entry_result.entry_reference_price,
        recent_swing_low=swing_low,
        recent_swing_high=swing_high,
        planning_allowed=True,
        warnings=entry_result.warnings,
        source_timestamps={"entry": entry_result.evaluated_at},
        metadata={"affordability_result_id": affordability.affordability_result_id},
    )
    stop_result = evaluate_stop_loss(
        trade_plan_input,
        policy,
        entry_result,
        stop_input,
    )

    if stop_result.status != "READY":
        return _blocked_result(
            planning_result_id=result_id,
            affordability=affordability,
            evaluated_at=now,
            status="BLOCKED",
            blockers=stop_result.blockers,
            entry_result=entry_result,
            stop_loss_result=stop_result,
            trade_plan_input_id=trade_plan_input.trade_plan_input_id,
            policy_id=policy.policy_id,
            warnings=tuple(
                dict.fromkeys(entry_result.warnings + stop_result.warnings)
            ),
        )

    target_input = ThreeTargetEvaluationInputV1(
        evaluation_id=target_id,
        evaluation_result_id=target_result_id,
        evaluated_at=now,
        trade_plan_input_id=trade_plan_input.trade_plan_input_id,
        policy_id=policy.policy_id,
        entry_evaluation_result_id=entry_result.evaluation_result_id,
        stop_evaluation_result_id=stop_result.evaluation_result_id,
        underlying_symbol=identity[0],
        exchange=identity[1],
        direction=affordability.direction,
        option_right=affordability.option_right,
        entry_reference_price=entry_result.entry_reference_price,
        stop_loss_price=stop_result.stop_loss_price,
        stop_distance=stop_result.stop_distance,
        stop_distance_fraction=stop_result.stop_distance_fraction,
        atr_value=atr,
        expected_move_value=expected_move,
        structure_target_1=structure_targets[0],
        structure_target_2=structure_targets[1],
        structure_target_3=structure_targets[2],
        resistance_levels=resistance,
        support_levels=support,
        planning_allowed=True,
        warnings=tuple(
            dict.fromkeys(entry_result.warnings + stop_result.warnings)
        ),
        source_timestamps={
            "entry": entry_result.evaluated_at,
            "stop": stop_result.evaluated_at,
        },
        metadata={"affordability_result_id": affordability.affordability_result_id},
    )
    target_result = evaluate_three_targets(target_input, policy)

    if target_result.status != "READY":
        return _blocked_result(
            planning_result_id=result_id,
            affordability=affordability,
            evaluated_at=now,
            status="BLOCKED",
            blockers=target_result.blockers,
            entry_result=entry_result,
            stop_loss_result=stop_result,
            target_result=target_result,
            trade_plan_input_id=trade_plan_input.trade_plan_input_id,
            policy_id=policy.policy_id,
            warnings=tuple(
                dict.fromkeys(
                    entry_result.warnings
                    + stop_result.warnings
                    + target_result.warnings
                )
            ),
        )

    return SelectedOptionEntryStopTargetPlanResultV1(
        planning_result_id=result_id,
        affordability_result_id=affordability.affordability_result_id,
        certification_result_id=affordability.certification_result_id,
        parent_cycle_id=affordability.parent_cycle_id,
        parent_decision_id=affordability.parent_decision_id,
        bridge_result_id=affordability.bridge_result_id,
        candidate_id=affordability.candidate_id,
        observation_id=affordability.observation_id,
        ranking_result_id=affordability.ranking_result_id,
        contract_id=affordability.contract_id,
        trade_plan_input_id=trade_plan_input.trade_plan_input_id,
        policy_id=policy.policy_id,
        evaluated_at=now,
        status="READY",
        planning_allowed=True,
        entry_result=entry_result,
        stop_loss_result=stop_result,
        target_result=target_result,
        blockers=(),
        warnings=tuple(
            dict.fromkeys(
                entry_result.warnings
                + stop_result.warnings
                + target_result.warnings
            )
        ),
    )
