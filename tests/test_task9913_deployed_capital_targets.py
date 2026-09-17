from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.contracts.three_target_evaluation_input_v1 import (
    ThreeTargetEvaluationInputV1,
)
from services.contracts.trade_planning_policy_v1 import (
    TradePlanningPolicyV1,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)
from services.paper_orchestration import certified_runtime_composition
from services.trade_planning.three_target_evaluator import (
    evaluate_three_targets,
)


NOW = datetime(2026, 8, 18, 9, 30, tzinfo=timezone.utc)


def _typed_shell(contract_type, **values):
    value = object.__new__(contract_type)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


def _task9_target_policy():
    return _typed_shell(
        TradePlanningPolicyV1,
        policy_id="TASK9-TARGET-POLICY",
        target_method="DEPLOYED_CAPITAL_RETURN",
        target_1_multiplier=0.15,
        target_2_multiplier=0.30,
        target_3_multiplier=0.50,
        target_1_allocation_fraction=0.34,
        target_2_allocation_fraction=0.33,
        target_3_allocation_fraction=0.33,
        minimum_reward_to_risk_t1=1.0,
        minimum_reward_to_risk_t2=1.0,
        minimum_reward_to_risk_t3=1.0,
    )


def _target_input():
    return _typed_shell(
        ThreeTargetEvaluationInputV1,
        evaluation_result_id="task9913-target-result",
        evaluation_id="task9913-target-input",
        evaluated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        direction="BULLISH",
        option_right="CALL",
        policy_id="TASK9-TARGET-POLICY",
        entry_evaluation_result_id="task9913-entry-result",
        stop_evaluation_result_id="task9913-stop-result",
        planning_allowed=True,
        entry_reference_price=100.0,
        stop_loss_price=90.0,
        stop_distance=10.0,
        stop_distance_fraction=0.10,
        blockers=(),
        warnings=(),
        source_timestamps={},
        metadata={},
    )


def test_task9_targets_equal_frozen_deployed_capital_returns():
    policy = _task9_target_policy()
    evaluation_input = _target_input()

    result = evaluate_three_targets(
        evaluation_input,
        policy,
    )

    assert result.status == "READY"
    assert result.target_method == "DEPLOYED_CAPITAL_RETURN"
    assert result.selected_target_source == "DEPLOYED_CAPITAL_RETURN"

    targets = (
        result.target_1,
        result.target_2,
        result.target_3,
    )
    expected_prices = (115.0, 130.0, 150.0)
    expected_returns = (0.15, 0.30, 0.50)

    assert tuple(
        target.target_price for target in targets
    ) == pytest.approx(expected_prices)

    # Quantity must not change the return percentage.  Deployed capital
    # here is premium outlay before the separate Task 9.92 cost authority.
    for quantity in (1, 25, 75, 150):
        deployed_capital = (
            evaluation_input.entry_reference_price * quantity
        )

        for target, expected_return in zip(
            targets,
            expected_returns,
        ):
            target_profit = (
                target.target_price
                - evaluation_input.entry_reference_price
            ) * quantity

            assert target_profit == pytest.approx(
                deployed_capital * expected_return
            )


def test_task9_composition_replaces_target_and_local_cost_authorities(
    monkeypatch,
):
    incoming_policy = _typed_shell(
        TradePlanningPolicyV1,
        policy_id="INHERITED-TASK8-POLICY",
    )

    inherited_cost_policy = SimpleNamespace(
        cost_policy_id="INHERITED-COST-POLICY",
    )

    inherited_cost_evidence = SimpleNamespace(
        planned_lot_count=2,
        lot_size=25,
        estimated_premium_outlay=5000.0,
    )

    inherited_input = SimpleNamespace(
        planning_input_id="planning-input-1",
        trade_plan_id="trade-plan-1",
        trading_cost_policy=inherited_cost_policy,
        trading_cost_evidence=inherited_cost_evidence,
        option_contract_selection_result=SimpleNamespace(
            selection_result_id="selection-1",
        ),
        evaluated_at=datetime(
            2026,
            8,
            18,
            10,
            0,
            tzinfo=timezone(
                timedelta(
                    hours=5,
                    minutes=30,
                )
            ),
        ),
        source_timestamps={},
        warnings=(),
    )

    incoming_bundle = _typed_shell(
        CertifiedP6InputBundleV1,
        planning_policy=incoming_policy,
        capital_quantity_input=inherited_input,
    )

    opportunity = SimpleNamespace(
        evidence={
            "certified_p6_input_bundle": incoming_bundle,
        }
    )

    task9_policy = SimpleNamespace(
        policy_id=incoming_policy.policy_id,
        target_method="DEPLOYED_CAPITAL_RETURN",
        target_1_multiplier=0.15,
        target_2_multiplier=0.30,
        target_3_multiplier=0.50,
    )

    task9_cost_evidence = SimpleNamespace(
        evidence_id="task9-local-cost-evidence",
    )

    task9_capital_input = SimpleNamespace()
    converted_bundle = SimpleNamespace()

    calls = []

    def fake_cost_evidence(**kwargs):
        policy = kwargs["policy"]

        assert policy.calculation_mode == (
            "FIXED_ASSUMPTION_MODEL"
        )
        assert policy.brokerage_fixed_per_order == pytest.approx(
            20.0
        )
        assert (
            policy.exchange_transaction_charge_fraction
            == pytest.approx(0.0005)
        )
        assert policy.clearing_charge_fraction == pytest.approx(
            0.0
        )
        assert policy.stt_rate_fraction == pytest.approx(
            0.000625
        )
        assert policy.sebi_charge_fraction == pytest.approx(
            0.000001
        )
        assert policy.stamp_duty_rate_fraction == pytest.approx(
            0.00003
        )
        assert policy.gst_rate_fraction == pytest.approx(
            0.18
        )
        assert policy.slippage_rate_fraction == pytest.approx(
            0.005
        )
        assert policy.estimated_order_count == 5
        assert policy.policy_source == (
            "TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"
        )

        assert kwargs["planned_lot_count"] == 2
        assert kwargs["lot_size"] == 25
        assert (
            kwargs["estimated_premium_outlay"]
            == pytest.approx(5000.0)
        )

        return task9_cost_evidence

    def fake_replace(value, **changes):
        calls.append((value, changes))

        if value is incoming_policy:
            assert changes == {
                "target_method": "DEPLOYED_CAPITAL_RETURN",
                "target_1_multiplier": 0.15,
                "target_2_multiplier": 0.30,
                "target_3_multiplier": 0.50,
            }
            return task9_policy

        if value is inherited_input:
            assert (
                changes["trading_cost_evidence"]
                is task9_cost_evidence
            )

            assert (
                changes["trading_cost_policy"].policy_source
                == "TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"
            )

            return task9_capital_input

        if value is incoming_bundle:
            assert changes == {
                "planning_policy": task9_policy,
                "capital_quantity_input": task9_capital_input,
            }

            return converted_bundle

        raise AssertionError(
            "unexpected Task9 replacement target"
        )

    monkeypatch.setattr(
        certified_runtime_composition,
        "calculate_task9_local_paper_cost_evidence",
        fake_cost_evidence,
    )

    monkeypatch.setattr(
        certified_runtime_composition,
        "replace",
        fake_replace,
    )

    result = (
        certified_runtime_composition
        ._p6_bundle_from_opportunity(
            object(),
            object(),
            opportunity,
        )
    )

    assert result is converted_bundle
    assert len(calls) == 3

    assert task9_policy.policy_id == incoming_policy.policy_id

    assert not hasattr(
        incoming_policy,
        "target_method",
    )

