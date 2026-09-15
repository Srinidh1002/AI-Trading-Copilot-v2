from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest

from services.certification.task8_selected_market_p6_bundle import (
    build_task8_selected_market_p6_bundle,
)
from services.contracts.capital_quantity_trading_cost_policy_v1 import (
    CapitalQuantityTradingCostPolicyV1,
)
from services.paper_orchestration import certified_runtime_composition
from services.paper_orchestration.certified_p6_input_factory import CertifiedP6InputBundleV1
from services.paper_orchestration.certified_runtime_composition import (
    _p6_bundle_from_opportunity,
)
from services.trade_planning.task9_local_paper_cost_authority import (
    TASK9_LOCAL_EVIDENCE_SOURCE,
    calculate_task9_local_paper_cost_evidence,
)
from test_task8_selected_market_p6_bundle import _real_selected_bundle_inputs


NOW = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)


def _policy(**changes):
    values = dict(
        cost_policy_id="task9-test-policy",
        calculation_mode="FIXED_ASSUMPTION_MODEL",
        brokerage_rate_fraction=0.01,
        brokerage_fixed_per_order=20.0,
        exchange_transaction_charge_fraction=0.02,
        clearing_charge_fraction=0.03,
        stt_rate_fraction=0.04,
        sebi_charge_fraction=0.05,
        stamp_duty_rate_fraction=0.06,
        gst_rate_fraction=0.10,
        slippage_rate_fraction=0.07,
        estimated_order_count=3,
        policy_timestamp=NOW,
        policy_source="TEST",
    )
    values.update(changes)
    return CapitalQuantityTradingCostPolicyV1(**values)


def _evidence(policy, **changes):
    values = dict(
        policy=policy,
        planning_input_id="input",
        trade_plan_id="plan",
        option_selection_result_id="selection",
        planned_lot_count=2,
        lot_size=25,
        estimated_premium_outlay=1000.0,
        evidence_timestamp=NOW,
    )
    values.update(changes)
    return calculate_task9_local_paper_cost_evidence(**values)


def test_local_authority_uses_deterministic_component_and_total_math():
    evidence = _evidence(_policy())

    assert evidence.planned_quantity == 50
    assert evidence.estimated_brokerage == 70.0  # 3 * 20 + 1% of premium
    assert evidence.estimated_exchange_transaction_charges == 20.0
    assert evidence.estimated_clearing_charges == 30.0
    assert evidence.estimated_stt == 40.0
    assert evidence.estimated_sebi_charges == 50.0
    assert evidence.estimated_stamp_duty == 60.0
    assert evidence.estimated_gst == 17.0  # 10% of brokerage + exchange + clearing + SEBI
    assert evidence.estimated_slippage == 70.0
    assert evidence.estimated_total_trading_cost == 357.0
    assert evidence.estimated_total_capital_requirement == 1357.0
    assert evidence.evidence_source == TASK9_LOCAL_EVIDENCE_SOURCE
    assert evidence.execution_mode == "PAPER"
    assert evidence.live_execution_eligible is False


def test_local_authority_honours_flags_caller_gst_base_and_quantity_coherence():
    policy = _policy(
        gst_taxable_base_mode="CALLER_SUPPLIED",
        apply_brokerage=False,
        apply_exchange_transaction_charges=False,
        apply_clearing_charges=False,
        apply_stt=False,
        apply_sebi_charges=False,
        apply_stamp_duty=False,
        apply_slippage=False,
    )
    evidence = _evidence(
        policy,
        planned_lot_count=3,
        lot_size=50,
        caller_supplied_gst_taxable_base=200.0,
    )

    assert evidence.planned_quantity == 150
    assert evidence.estimated_gst == 20.0
    assert evidence.estimated_total_trading_cost == 20.0
    assert evidence.estimated_total_capital_requirement == 1020.0
    assert all(
        getattr(evidence, name) == 0.0
        for name in (
            "estimated_brokerage", "estimated_exchange_transaction_charges",
            "estimated_clearing_charges", "estimated_stt", "estimated_sebi_charges",
            "estimated_stamp_duty", "estimated_slippage",
        )
    )


def test_task9_composition_replaces_task8_cost_objects_without_mutation(
    monkeypatch,
):
    incoming_planning_policy = object()

    inherited_policy = _policy(
        cost_policy_id="task8-inherited-cost-policy",
        brokerage_fixed_per_order=999.0,
        exchange_transaction_charge_fraction=0.50,
        stt_rate_fraction=0.50,
        slippage_rate_fraction=0.50,
        estimated_order_count=99,
        policy_source="TASK8_TEST_INHERITED",
    )

    inherited_evidence = SimpleNamespace(
        planned_lot_count=2,
        lot_size=25,
        planned_quantity=50,
        estimated_premium_outlay=1000.0,
        evidence_source="TASK8_FIXED_ASSUMPTION_MODEL",
    )

    inherited_selection = SimpleNamespace(
        selection_result_id="task8-selection",
    )

    inherited_input = SimpleNamespace(
        planning_input_id="task9-cost-input",
        trade_plan_id="task9-trade-plan",
        option_contract_selection_result=inherited_selection,
        trading_cost_policy=inherited_policy,
        trading_cost_evidence=inherited_evidence,
        evaluated_at=NOW,
        warnings=("UPSTREAM_WARNING",),
        source_timestamps={"candidate": NOW},
    )

    bundle = object.__new__(CertifiedP6InputBundleV1)
    object.__setattr__(
        bundle,
        "planning_policy",
        incoming_planning_policy,
    )
    object.__setattr__(
        bundle,
        "capital_quantity_input",
        inherited_input,
    )

    opportunity = SimpleNamespace(
        evidence={
            "certified_p6_input_bundle": bundle,
        }
    )

    task9_planning_policy = SimpleNamespace(
        target_method="DEPLOYED_CAPITAL_RETURN",
        target_1_multiplier=0.15,
        target_2_multiplier=0.30,
        target_3_multiplier=0.50,
    )

    converted_capital_input = SimpleNamespace()
    converted_bundle = SimpleNamespace()

    captured = {}

    def fake_replace(value, **changes):
        if value is incoming_planning_policy:
            assert changes == {
                "target_method": "DEPLOYED_CAPITAL_RETURN",
                "target_1_multiplier": 0.15,
                "target_2_multiplier": 0.30,
                "target_3_multiplier": 0.50,
            }
            return task9_planning_policy

        if value is inherited_input:
            captured["cost_policy"] = changes["trading_cost_policy"]
            captured["cost_evidence"] = changes["trading_cost_evidence"]

            assert set(changes) == {
                "trading_cost_policy",
                "trading_cost_evidence",
            }
            return converted_capital_input

        if value is bundle:
            assert changes == {
                "planning_policy": task9_planning_policy,
                "capital_quantity_input": converted_capital_input,
            }
            return converted_bundle

        raise AssertionError(
            f"unexpected replace target: {type(value)!r}"
        )

    monkeypatch.setattr(
        certified_runtime_composition,
        "replace",
        fake_replace,
    )

    result = (
        certified_runtime_composition
        ._p6_bundle_from_opportunity(
            None,
            None,
            opportunity,
        )
    )

    assert result is converted_bundle

    task9_policy = captured["cost_policy"]
    task9_evidence = captured["cost_evidence"]

    assert task9_policy is not inherited_policy
    assert task9_evidence is not inherited_evidence

    assert (
        task9_policy.cost_policy_id
        == "task9-local-cost-policy:task9-cost-input"
    )
    assert task9_policy.calculation_mode == "FIXED_ASSUMPTION_MODEL"
    assert (
        task9_policy.policy_source
        == "TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"
    )

    assert task9_policy.brokerage_fixed_per_order == pytest.approx(20.0)
    assert (
        task9_policy.exchange_transaction_charge_fraction
        == pytest.approx(0.0005)
    )
    assert task9_policy.clearing_charge_fraction == pytest.approx(0.0)
    assert task9_policy.stt_rate_fraction == pytest.approx(0.000625)
    assert task9_policy.sebi_charge_fraction == pytest.approx(0.000001)
    assert task9_policy.stamp_duty_rate_fraction == pytest.approx(0.00003)
    assert task9_policy.gst_rate_fraction == pytest.approx(0.18)
    assert task9_policy.slippage_rate_fraction == pytest.approx(0.005)
    assert task9_policy.estimated_order_count == 5

    assert (
        task9_evidence.evidence_source
        == "TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"
    )
    assert task9_evidence.planning_input_id == "task9-cost-input"
    assert task9_evidence.trade_plan_id == "task9-trade-plan"
    assert (
        task9_evidence.option_selection_result_id
        == "task8-selection"
    )

    assert task9_evidence.planned_lot_count == 2
    assert task9_evidence.lot_size == 25
    assert task9_evidence.planned_quantity == 50
    assert task9_evidence.estimated_premium_outlay == pytest.approx(
        1000.0
    )

    assert task9_evidence.estimated_brokerage == pytest.approx(100.0)
    assert (
        task9_evidence.estimated_exchange_transaction_charges
        == pytest.approx(0.5)
    )
    assert task9_evidence.estimated_clearing_charges == pytest.approx(0.0)
    assert task9_evidence.estimated_stt == pytest.approx(0.625)
    assert task9_evidence.estimated_sebi_charges == pytest.approx(0.001)
    assert task9_evidence.estimated_stamp_duty == pytest.approx(0.03)
    assert task9_evidence.estimated_gst == pytest.approx(18.09018)
    assert task9_evidence.estimated_slippage == pytest.approx(5.0)

    expected_total_cost = 124.24618

    assert task9_evidence.estimated_total_trading_cost == pytest.approx(
        expected_total_cost
    )
    assert (
        task9_evidence.estimated_total_capital_requirement
        == pytest.approx(1000.0 + expected_total_cost)
    )

    assert task9_evidence.execution_mode == "PAPER"
    assert task9_evidence.live_execution_eligible is False

    # The inherited Task 8 objects remain unchanged.
    assert inherited_input.trading_cost_policy is inherited_policy
    assert inherited_input.trading_cost_evidence is inherited_evidence

    assert inherited_policy.cost_policy_id == "task8-inherited-cost-policy"
    assert inherited_evidence.evidence_source == (
        "TASK8_FIXED_ASSUMPTION_MODEL"
    )

