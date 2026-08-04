from dataclasses import replace
from datetime import date

import pytest

from services.contracts.capital_quantity_planning_input_v1 import (
    CapitalQuantityPlanningInputV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.option_contract_selection_input_v1 import (
    OptionContractSelectionInputV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
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
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    execute_selected_market_p6_planning,
)
from test_selected_market_planning_bridge import selected_decision


def _exact(contract, **attributes):
    value = object.__new__(contract)
    for name, item in attributes.items():
        object.__setattr__(value, name, item)
    return value


def _selected_cycle(decision):
    selected = next(
        entry
        for entry in decision.entries
        if entry.outcome_reason == "SELECTED"
    )
    candidate = selected.child.candidate

    return _exact(
        PaperOrchestrationCycleInputV1,
        underlying_symbol=candidate.underlying_symbol,
        exchange=candidate.exchange,
        observation_id=candidate.observation_id,
        p6_integration_id="r33-p6-integration",
    )


def _bundle(decision):
    selected = next(
        entry
        for entry in decision.entries
        if entry.outcome_reason == "SELECTED"
    )
    candidate = selected.child.candidate
    ranking = candidate.option_contract_eligibility
    market = (
        candidate.underlying_symbol,
        candidate.exchange,
    )
    direction = candidate.direction
    right = "CALL" if direction == "BULLISH" else "PUT"

    policy = _exact(
        TradePlanningPolicyV1,
        policy_id="r33-policy",
    )

    opportunity = type(
        "SelectedOpportunity",
        (),
        {"directional_bias": direction},
    )()

    canonical = type(
        "CanonicalPlan",
        (),
        {
            "underlying_symbol": market[0],
            "exchange": market[1],
            "direction": direction,
            "selected_market_opportunity": opportunity,
        },
    )()

    selection = _exact(
        OptionContractSelectionInputV1,
        policy_id="r33-policy",
        underlying_symbol=market[0],
        exchange=market[1],
        direction=direction,
        option_right=right,
        option_ranking_result=ranking,
        option_ranking_result_id=ranking.ranking_id,
    )

    entry = _exact(
        EntryZoneEvaluationInputV1,
        policy_id="r33-policy",
        underlying_symbol=market[0],
        exchange=market[1],
        direction=direction,
    )
    stop = _exact(
        StopLossEvaluationInputV1,
        policy_id="r33-policy",
        underlying_symbol=market[0],
        exchange=market[1],
        direction=direction,
    )
    targets = _exact(
        ThreeTargetEvaluationInputV1,
        policy_id="r33-policy",
        underlying_symbol=market[0],
        exchange=market[1],
        direction=direction,
    )
    capital = _exact(
        CapitalQuantityPlanningInputV1,
        canonical_trade_plan_input=canonical,
    )

    return CertifiedP6InputBundleV1(
        planning_policy=policy,
        option_selection_input=selection,
        entry_zone_input=entry,
        stop_loss_input=stop,
        three_target_input=targets,
        capital_quantity_input=capital,
    )


def _integrated(status="READY", blockers=()):
    return IntegratedThreeTargetTradePlanResultV1(
        integration_id="r33-integrated",
        status=status,
        canonical_trade_plan_input=None,
        entry_zone_result=None,
        stop_loss_result=None,
        three_target_result=None,
        option_contract_selection_result=None,
        capital_quantity_result=None,
        blockers=blockers,
    )


def _execute(
    *,
    decision=None,
    cycle=None,
    bundle=None,
    authority=None,
):
    selected_decision_value = decision or selected_decision()
    return execute_selected_market_p6_planning(
        bridge_result_id="r33-ready-bridge",
        decision=selected_decision_value,
        selected_cycle=(
            cycle
            if cycle is not None
            else _selected_cycle(selected_decision_value)
        ),
        certified_p6_input_bundle=(
            bundle
            if bundle is not None
            else _bundle(selected_decision_value)
        ),
        evaluated_at=selected_decision_value.completed_at,
        maximum_candidate_age_seconds=180.0,
        p6_stage_authority=authority or (
            lambda _: _integrated()
        ),
    )


def test_exact_selected_bundle_reaches_p6_once_and_is_ready():
    decision = selected_decision()
    cycle = _selected_cycle(decision)
    bundle = _bundle(decision)
    calls = []

    def authority(stage_input):
        calls.append(stage_input)
        return _integrated()

    result = _execute(
        decision=decision,
        cycle=cycle,
        bundle=bundle,
        authority=authority,
    )

    assert result.status == "READY"
    assert result.blockers == ()
    assert result.planning_result.status == "READY"
    assert len(calls) == 1

    stage_input = calls[0]
    assert stage_input.integration_id == cycle.p6_integration_id
    assert (
        stage_input.option_selection_input.option_ranking_result
        is next(
            entry
            for entry in decision.entries
            if entry.outcome_reason == "SELECTED"
        ).child.candidate.option_contract_eligibility
    )
    assert result.bridge.selected_market == (
        cycle.underlying_symbol,
        cycle.exchange,
    )


def test_nonready_p6_result_fails_closed_without_geometry():
    result = _execute(
        authority=lambda _: _integrated(
            status="BLOCKED",
            blockers=("P6_POLICY_BLOCKED",),
        )
    )

    assert result.status == "BLOCKED"
    assert result.planning_result is None
    assert result.blockers == ("P6_POLICY_BLOCKED",)


def test_selected_cycle_market_tamper_stops_before_p6():
    decision = selected_decision()
    cycle = _selected_cycle(decision)
    object.__setattr__(cycle, "underlying_symbol", "SENSEX")
    calls = []

    with pytest.raises(
        ValueError,
        match="selected cycle market mismatch",
    ):
        _execute(
            decision=decision,
            cycle=cycle,
            authority=lambda value: calls.append(value),
        )

    assert calls == []


def test_selected_cycle_observation_tamper_stops_before_p6():
    decision = selected_decision()
    cycle = _selected_cycle(decision)
    object.__setattr__(cycle, "observation_id", "tampered")
    calls = []

    with pytest.raises(
        ValueError,
        match="selected cycle observation identity mismatch",
    ):
        _execute(
            decision=decision,
            cycle=cycle,
            authority=lambda value: calls.append(value),
        )

    assert calls == []


def test_bundle_option_right_tamper_stops_before_p6():
    decision = selected_decision()
    bundle = _bundle(decision)
    selection = bundle.option_selection_input
    object.__setattr__(
        selection,
        "option_right",
        "PUT" if selection.option_right == "CALL" else "CALL",
    )
    calls = []

    with pytest.raises(
        ValueError,
        match="P6 bundle option right mismatch",
    ):
        _execute(
            decision=decision,
            bundle=bundle,
            authority=lambda value: calls.append(value),
        )

    assert calls == []


def test_bundle_ranking_object_tamper_stops_before_p6():
    decision = selected_decision()
    bundle = _bundle(decision)
    selection = bundle.option_selection_input
    object.__setattr__(
        selection,
        "option_ranking_result",
        replace(
            selection.option_ranking_result,
            ranking_id="tampered-ranking",
        ),
    )
    calls = []

    with pytest.raises(
        ValueError,
        match="must retain selected candidate option ranking",
    ):
        _execute(
            decision=decision,
            bundle=bundle,
            authority=lambda value: calls.append(value),
        )

    assert calls == []
