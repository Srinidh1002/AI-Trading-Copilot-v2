from datetime import datetime, timezone
from importlib import import_module
from unittest.mock import patch

from services.contracts.capital_quantity_planning_result_v1 import (
    CapitalQuantityPlanningResultV1,
)
from services.contracts.entry_zone_evaluation_result_v1 import (
    EntryZoneEvaluationResultV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.option_contract_selection_result_v1 import (
    OptionContractSelectionResultV1,
)
from services.contracts.stop_loss_evaluation_result_v1 import (
    StopLossEvaluationResultV1,
)
from services.contracts.three_target_evaluation_result_v1 import (
    ThreeTargetEvaluationResultV1,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def test_executor_invokes_certified_p6_boundaries_in_order():
    module = import_module(
        "services.paper_orchestration.p6_planning_stage_executor"
    )

    stage_input = object.__new__(module.P6PlanningStageInputV1)
    object.__setattr__(stage_input, "planning_policy", object())

    capital_template = type(
        "CapitalTemplate",
        (),
        {
            "canonical_trade_plan_input": object(),
            "planning_input_id": "capital-input-1",
            "trade_plan_id": "trade-plan-1",
            "policy_id": "capital-policy-1",
            "capital_quantity_policy": object(),
            "trading_cost_policy": object(),
            "trading_cost_evidence": None,
            "caller_supplied_per_lot_risk_amount": None,
            "evaluated_at": NOW,
            "input_source": "TEST",
            "blockers": (),
            "warnings": (),
            "source_timestamps": {},
            "metadata": {},
        },
    )()

    object.__setattr__(
        stage_input,
        "capital_quantity_input",
        capital_template,
    )
    object.__setattr__(
        stage_input,
        "option_selection_input",
        object(),
    )
    object.__setattr__(
        stage_input,
        "entry_zone_input",
        object(),
    )
    object.__setattr__(
        stage_input,
        "stop_loss_input",
        object(),
    )
    object.__setattr__(
        stage_input,
        "three_target_input",
        object(),
    )
    object.__setattr__(
        stage_input,
        "integration_id",
        "integration-1",
    )

    order: list[str] = []

    option_result = object.__new__(
        OptionContractSelectionResultV1
    )
    entry_result = object.__new__(
        EntryZoneEvaluationResultV1
    )
    stop_result = object.__new__(
        StopLossEvaluationResultV1
    )
    target_result = object.__new__(
        ThreeTargetEvaluationResultV1
    )
    capital_result = object.__new__(
        CapitalQuantityPlanningResultV1
    )
    integrated_result = object.__new__(
        IntegratedThreeTargetTradePlanResultV1
    )

    with (
        patch.object(
            module,
            "select_option_contract",
            side_effect=lambda *_: (
                order.append("OPTION") or option_result
            ),
        ),
        patch.object(
            module,
            "evaluate_entry_zone",
            side_effect=lambda *_: (
                order.append("ENTRY") or entry_result
            ),
        ),
        patch.object(
            module,
            "evaluate_stop_loss",
            side_effect=lambda *_: (
                order.append("STOP") or stop_result
            ),
        ),
        patch.object(
            module,
            "evaluate_three_targets",
            side_effect=lambda *_: (
                order.append("TARGETS") or target_result
            ),
        ),
        patch.object(
            module,
            "CapitalQuantityPlanningInputV1",
            return_value=object(),
        ),
        patch.object(
            module,
            "plan_capital_quantity",
            side_effect=lambda *_: (
                order.append("CAPITAL") or capital_result
            ),
        ),
        patch.object(
            module,
            "IntegratedThreeTargetTradePlanInputV1",
            return_value=object(),
        ),
        patch.object(
            module,
            "integrate_three_target_trade_plan",
            side_effect=lambda *_: (
                order.append("INTEGRATE") or integrated_result
            ),
        ),
    ):
        result = module.execute_p6_planning_stage(stage_input)

    assert result is integrated_result
    assert order == [
        "OPTION",
        "ENTRY",
        "STOP",
        "TARGETS",
        "CAPITAL",
        "INTEGRATE",
    ]


def test_executor_module_does_not_import_live_execution():
    import sys

    import_module(
        "services.paper_orchestration.p6_planning_stage_executor"
    )

    forbidden = {
        "services.live.live_market_engine",
        "services.execution.order_executor",
        "services.execution.order_manager",
    }

    assert forbidden.isdisjoint(sys.modules)