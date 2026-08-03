"""Task 5 quantity sizing and executable PAPER plan assembly."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.trade_planning.executable_paper_trade_plan_assembler import (
    assemble_executable_paper_trade_plan,
)
from test_selected_option_affordability_risk_planner import certified, plan
from test_selected_option_entry_stop_target_planner import run


def upstream(symbol="NIFTY", direction="BULLISH"):
    affordability = plan(certified(symbol, direction))
    task4 = run(
        affordability=affordability,
    )
    return affordability, task4


def assemble(affordability=None, task4=None, **changes):
    if affordability is None or task4 is None:
        default_affordability, default_task4 = upstream()
        affordability = affordability or default_affordability
        task4 = task4 or default_task4
    defaults = dict(
        executable_plan_id="executable-plan-1",
        affordability=affordability,
        task4=task4,
        evaluated_at=affordability.evaluated_at,
        minimum_lot_count=1,
        maximum_lot_count=3,
        estimated_costs_per_lot=50.0,
        target_allocation_enabled=True,
        target_allocation_weights=(0.3, 0.4, 0.3),
        reserve_runner_lots=0,
    )
    defaults.update(changes)
    return assemble_executable_paper_trade_plan(**defaults)


def test_ready_plan_has_quantity_capital_risk_and_targets():
    affordability, task4 = upstream()
    result = assemble(affordability, task4)

    assert result.status == "READY"
    assert result.executable is True
    assert result.planned_lot_count == 3
    assert result.planned_quantity == 75
    assert result.risk_per_unit == 10.0
    assert result.risk_per_lot == 300.0
    assert result.estimated_premium_outlay == 7_500.0
    assert result.estimated_total_costs == 150.0
    assert result.estimated_total_capital_requirement == 7_650.0
    assert result.estimated_maximum_loss == 900.0
    assert (
        result.target_1_lot_count,
        result.target_2_lot_count,
        result.target_3_lot_count,
        result.runner_lot_count,
    ) == (1, 1, 1, 0)


@pytest.mark.parametrize(
    ("symbol", "direction", "right"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_both_markets_and_directions(symbol, direction, right):
    affordability, task4 = upstream(symbol, direction)
    result = assemble(affordability, task4)

    assert result.status == "READY"
    assert result.selected_market[0] == symbol
    assert result.direction == direction
    assert result.option_right == right


def test_full_trace_chain_is_preserved():
    affordability, task4 = upstream()
    result = assemble(affordability, task4)

    assert result.task4_planning_result_id == task4.planning_result_id
    assert result.affordability_result_id == affordability.affordability_result_id
    assert result.certification_result_id == affordability.certification_result_id
    assert result.parent_cycle_id == affordability.parent_cycle_id
    assert result.parent_decision_id == affordability.parent_decision_id
    assert result.bridge_result_id == affordability.bridge_result_id
    assert result.candidate_id == affordability.candidate_id
    assert result.observation_id == affordability.observation_id
    assert result.ranking_result_id == affordability.ranking_result_id
    assert result.contract_id == affordability.contract_id


def test_risk_authority_limits_lots():
    affordability, task4 = upstream()
    limited = replace(
        affordability,
        maximum_new_loss=550.0,
    )
    result = assemble(limited, task4)

    assert result.status == "READY"
    assert result.risk_based_lot_limit == 1
    assert result.planned_lot_count == 1
    assert result.estimated_maximum_loss == 300.0


def test_minimum_lot_count_failure_blocks():
    affordability, task4 = upstream()
    limited = replace(
        affordability,
        maximum_new_loss=550.0,
    )
    result = assemble(
        limited,
        task4,
        minimum_lot_count=2,
    )

    assert result.status == "BLOCKED"
    assert result.executable is False
    assert "MINIMUM_LOT_COUNT_NOT_MET" in result.blockers


def test_upstream_not_ready_is_unavailable():
    affordability, task4 = upstream()
    blocked = replace(
        task4,
        status="BLOCKED",
        planning_allowed=False,
        blockers=("TASK4_BLOCKED",),
    )
    result = assemble(affordability, blocked)

    assert result.status == "UNAVAILABLE"
    assert result.contract_id is None
    assert result.blockers == (
        "TASK5_UPSTREAM_NOT_READY",
        "TASK4_BLOCKED",
    )


def test_task4_affordability_mismatch_blocks():
    affordability, task4 = upstream()
    mismatched = replace(
        task4,
        affordability_result_id="other-affordability",
    )
    result = assemble(affordability, mismatched)

    assert result.status == "BLOCKED"
    assert "TASK5_AFFORDABILITY_ID_MISMATCH" in result.blockers


def test_runner_reservation_and_allocation():
    affordability, task4 = upstream()
    result = assemble(
        affordability,
        task4,
        reserve_runner_lots=1,
    )

    assert result.planned_lot_count == 3
    assert result.runner_lot_count == 1
    assert (
        result.target_1_lot_count
        + result.target_2_lot_count
        + result.target_3_lot_count
    ) == 2


def test_disabled_target_allocation_assigns_all_to_runner():
    affordability, task4 = upstream()
    result = assemble(
        affordability,
        task4,
        target_allocation_enabled=False,
    )

    assert result.target_1_lot_count == 0
    assert result.target_2_lot_count == 0
    assert result.target_3_lot_count == 0
    assert result.runner_lot_count == result.planned_lot_count


def test_costs_are_included_in_capital_and_maximum_loss():
    affordability, task4 = upstream()
    result = assemble(
        affordability,
        task4,
        estimated_costs_per_lot=100.0,
    )

    assert result.risk_per_lot == 350.0
    assert result.estimated_total_costs == 300.0
    assert result.estimated_maximum_loss == 1_050.0


def test_deterministic_and_does_not_mutate_inputs():
    affordability, task4 = upstream()
    before = (affordability.to_json(), task4.to_json())

    first = assemble(affordability, task4)
    second = assemble(affordability, task4)

    assert first.to_json() == second.to_json()
    assert before == (affordability.to_json(), task4.to_json())


def test_wrong_exact_types_are_rejected():
    affordability, task4 = upstream()
    with pytest.raises(TypeError, match="affordability"):
        assemble_executable_paper_trade_plan(
            executable_plan_id="plan",
            affordability=object(),
            task4=task4,
            evaluated_at=affordability.evaluated_at,
        )
    with pytest.raises(TypeError, match="task4"):
        assemble_executable_paper_trade_plan(
            executable_plan_id="plan",
            affordability=affordability,
            task4=object(),
            evaluated_at=affordability.evaluated_at,
        )


def test_no_provider_broker_lifecycle_or_persistence_dependencies():
    source = Path(
        "services/trade_planning/"
        "executable_paper_trade_plan_assembler.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "provider",
        "broker",
        "paper_trading",
        "paper_portfolio",
        "persistence",
        "repository",
        "requests",
        "dashboard",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
        "time.sleep(",
    ):
        assert token not in source
