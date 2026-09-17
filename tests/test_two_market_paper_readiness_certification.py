"""Task 7 end-to-end two-market PAPER readiness certification."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.paper_orchestration.executable_plan_lifecycle_adapter import (
    adapt_executable_plan_to_paper_lifecycle,
)
from services.trade_planning.executable_paper_trade_plan_assembler import (
    assemble_executable_paper_trade_plan,
)
from test_selected_option_contract_certifier import certify, ready_bridge
from test_selected_option_affordability_risk_planner import plan
from test_selected_option_entry_stop_target_planner import run


def certify_full_chain(
    symbol="NIFTY",
    direction="BULLISH",
    *,
    available_capital=100_000.0,
    maximum_daily_loss=3_000.0,
    realized_daily_loss=500.0,
    maximum_lot_count=3,
):
    bridge = ready_bridge(symbol, direction)
    contract = certify(bridge)
    affordability = plan(
        contract,
        available_capital=available_capital,
        maximum_daily_loss=maximum_daily_loss,
        realized_daily_loss=realized_daily_loss,
    )
    geometry = run(affordability=affordability)
    executable = assemble_executable_paper_trade_plan(
        executable_plan_id=f"task7-{symbol}-{direction}",
        affordability=affordability,
        task4=geometry,
        evaluated_at=affordability.evaluated_at,
        minimum_lot_count=1,
        maximum_lot_count=maximum_lot_count,
        estimated_costs_per_lot=50.0,
        target_allocation_enabled=True,
        target_allocation_weights=(0.3, 0.4, 0.3),
        reserve_runner_lots=0,
    )
    lifecycle = adapt_executable_plan_to_paper_lifecycle(executable)
    return bridge, contract, affordability, geometry, executable, lifecycle


@pytest.mark.parametrize(
    ("symbol", "direction", "right", "exchange"),
    (
        ("NIFTY", "BULLISH", "CALL", "NSE"),
        ("NIFTY", "BEARISH", "PUT", "NSE"),
        ("SENSEX", "BULLISH", "CALL", "BSE"),
        ("SENSEX", "BEARISH", "PUT", "BSE"),
    ),
)
def test_complete_two_market_paper_chain_is_ready(
    symbol,
    direction,
    right,
    exchange,
):
    (
        bridge,
        contract,
        affordability,
        geometry,
        executable,
        lifecycle,
    ) = certify_full_chain(symbol, direction)

    assert bridge.action == right
    assert bridge.selected_market == (symbol, exchange)
    assert bridge.planning_allowed is True

    assert contract.status == "CERTIFIED"
    assert contract.selected_market == (symbol, exchange)
    assert contract.direction == direction
    assert contract.option_right == right

    assert affordability.status == "READY"
    assert affordability.planning_allowed is True
    assert affordability.contract_id == contract.contract_id

    assert geometry.status == "READY"
    assert geometry.planning_allowed is True
    assert geometry.contract_id == contract.contract_id

    assert executable.status == "READY"
    assert executable.executable is True
    assert executable.selected_market == (symbol, exchange)
    assert executable.direction == direction
    assert executable.option_right == right
    assert executable.planned_lot_count >= 1
    assert executable.planned_quantity == (
        executable.planned_lot_count * executable.lot_size
    )
    assert executable.estimated_total_capital_requirement <= (
        affordability.deployable_capital
    )
    assert executable.estimated_maximum_loss <= (
        affordability.maximum_new_loss
    )

    assert lifecycle.status == "READY"
    assert lifecycle.integration_id == executable.executable_plan_id
    assert lifecycle.capital_quantity_result.planned_quantity == (
        executable.planned_quantity
    )
    assert lifecycle.capital_quantity_result.estimated_risk_amount == (
        executable.estimated_maximum_loss
    )


def test_selected_market_trace_remains_exact_through_final_handoff():
    (
        bridge,
        contract,
        affordability,
        geometry,
        executable,
        lifecycle,
    ) = certify_full_chain("SENSEX", "BEARISH")

    assert contract.parent_cycle_id == bridge.parent_cycle_id
    assert contract.parent_decision_id == bridge.parent_decision_id
    assert contract.bridge_result_id == bridge.bridge_result_id
    assert contract.candidate_id == bridge.candidate_id
    assert contract.observation_id == bridge.observation_id

    assert affordability.certification_result_id == (
        contract.certification_result_id
    )
    assert geometry.affordability_result_id == (
        affordability.affordability_result_id
    )
    assert executable.task4_planning_result_id == (
        geometry.planning_result_id
    )
    assert executable.affordability_result_id == (
        affordability.affordability_result_id
    )

    assert lifecycle.metadata["certification_result_id"] == (
        contract.certification_result_id
    )
    assert lifecycle.metadata["affordability_result_id"] == (
        affordability.affordability_result_id
    )
    assert lifecycle.metadata["task4_planning_result_id"] == (
        geometry.planning_result_id
    )


def test_losing_market_never_reaches_contract_or_quantity_planning():
    (
        bridge,
        contract,
        affordability,
        geometry,
        executable,
        lifecycle,
    ) = certify_full_chain("NIFTY", "BULLISH")

    assert bridge.losing_market == ("SENSEX", "BSE")
    assert bridge.losing_market != contract.selected_market
    assert bridge.losing_market != affordability.selected_market
    assert bridge.losing_market != executable.selected_market
    assert lifecycle.option_contract_selection_result.underlying_symbol == (
        "NIFTY"
    )


def test_capital_insufficiency_fails_closed_before_geometry_and_execution():
    bridge = ready_bridge("NIFTY", "BULLISH")
    contract = certify(bridge)
    affordability = plan(
        contract,
        available_capital=2_000.0,
        maximum_daily_loss=1_000.0,
        realized_daily_loss=0.0,
    )
    geometry = run(affordability=affordability)

    assert affordability.status == "BLOCKED"
    assert affordability.planning_allowed is False
    assert geometry.status == "UNAVAILABLE"
    assert geometry.planning_allowed is False
    assert geometry.entry_result is None
    assert "CAPITAL_INSUFFICIENT_FOR_ONE_LOT" in affordability.blockers


def test_risk_budget_controls_final_quantity():
    (
        _,
        _,
        affordability,
        _,
        executable,
        _,
    ) = certify_full_chain(
        "NIFTY",
        "BULLISH",
        maximum_daily_loss=1_100.0,
        realized_daily_loss=500.0,
        maximum_lot_count=10,
    )

    assert affordability.maximum_new_loss == 600.0
    assert executable.risk_per_lot == 300.0
    assert executable.planned_lot_count == 2
    assert executable.estimated_maximum_loss == 600.0


def test_final_geometry_and_allocation_are_complete():
    (
        _,
        _,
        _,
        geometry,
        executable,
        lifecycle,
    ) = certify_full_chain()

    assert geometry.entry_result.entry_reference_price == 100.0
    assert geometry.stop_loss_result.stop_loss_price == 90.0
    assert tuple(
        target.target_price
        for target in (
            geometry.target_result.target_1,
            geometry.target_result.target_2,
            geometry.target_result.target_3,
        )
    ) == (110.0, 115.0, 120.0)

    assert sum(
        (
            executable.target_1_lot_count,
            executable.target_2_lot_count,
            executable.target_3_lot_count,
            executable.runner_lot_count,
        )
    ) == executable.planned_lot_count

    capital = lifecycle.capital_quantity_result
    assert (
        capital.target_1_lot_count,
        capital.target_2_lot_count,
        capital.target_3_lot_count,
        capital.runner_lot_count,
    ) == (
        executable.target_1_lot_count,
        executable.target_2_lot_count,
        executable.target_3_lot_count,
        executable.runner_lot_count,
    )


def test_entire_chain_is_deterministic():
    first = certify_full_chain("SENSEX", "BEARISH")
    second = certify_full_chain("SENSEX", "BEARISH")

    assert tuple(item.to_json() for item in first[1:]) == tuple(
        item.to_json() for item in second[1:]
    )


def test_every_certified_stage_remains_paper_only():
    values = certify_full_chain()
    for value in values:
        assert value.execution_mode == "PAPER"
        assert value.live_execution_eligible is False
        assert getattr(value, "broker_order_submission", False) is False


def test_certification_surface_has_no_live_or_broker_side_effects():
    paths = (
        "services/trade_planning/selected_market_planning_bridge.py",
        "services/trade_planning/selected_option_contract_certifier.py",
        "services/trade_planning/selected_option_affordability_risk_planner.py",
        "services/trade_planning/selected_option_entry_stop_target_planner.py",
        "services/trade_planning/executable_paper_trade_plan_assembler.py",
        "services/paper_orchestration/executable_plan_lifecycle_adapter.py",
    )
    forbidden_imports = (
        "services.execution",
        "services.broker",
        "services.paper_trading",
        "services.paper_portfolio",
        "requests",
        "socket",
    )
    forbidden_tokens = (
        "place_order(",
        "submit_order(",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
        "time.sleep(",
    )

    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        assert not any(
            module == forbidden
            or module.startswith(forbidden + ".")
            for module in imports
            for forbidden in forbidden_imports
        )
        assert not any(token in source for token in forbidden_tokens)


def test_task7_certification_does_not_mutate_upstream_values():
    bridge = ready_bridge()
    contract = certify(bridge)
    before = (repr(bridge), contract.to_json())

    affordability = plan(contract)
    geometry = run(affordability=affordability)
    executable = assemble_executable_paper_trade_plan(
        executable_plan_id="task7-mutation-check",
        affordability=affordability,
        task4=geometry,
        evaluated_at=affordability.evaluated_at,
        minimum_lot_count=1,
        maximum_lot_count=3,
        estimated_costs_per_lot=50.0,
        target_allocation_enabled=True,
        target_allocation_weights=(0.3, 0.4, 0.3),
        reserve_runner_lots=0,
    )
    adapt_executable_plan_to_paper_lifecycle(executable)

    assert before == (repr(bridge), contract.to_json())


