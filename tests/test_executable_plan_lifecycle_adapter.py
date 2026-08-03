"""Task 6 PAPER portfolio and lifecycle compatibility handoff."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.paper_orchestration.executable_plan_lifecycle_adapter import (
    adapt_executable_plan_to_paper_lifecycle,
)
from test_executable_paper_trade_plan_assembler import assemble, upstream


def executable(symbol="NIFTY", direction="BULLISH"):
    affordability, task4 = upstream(symbol, direction)
    return assemble(affordability, task4)


def test_ready_task5_plan_adapts_to_exact_integrated_contract():
    source = executable()
    result = adapt_executable_plan_to_paper_lifecycle(source)

    assert type(result) is IntegratedThreeTargetTradePlanResultV1
    assert result.status == "READY"
    assert result.integration_id == source.executable_plan_id
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


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
    source = executable(symbol, direction)
    result = adapt_executable_plan_to_paper_lifecycle(source)
    selection = result.option_contract_selection_result
    contract = selection.selected_contract.contract

    assert (selection.underlying_symbol, selection.exchange) == (
        symbol,
        source.selected_market[1],
    )
    assert selection.direction == direction
    assert selection.option_right == right
    assert contract.contract_id == source.contract_id
    assert contract.trading_symbol == source.trading_symbol
    assert contract.instrument_token == source.instrument_token


def test_quantity_capital_risk_costs_and_allocations_are_copied():
    source = executable()
    result = adapt_executable_plan_to_paper_lifecycle(source)
    capital = result.capital_quantity_result

    assert capital.trade_plan_id == source.executable_plan_id
    assert capital.planned_lot_count == source.planned_lot_count
    assert capital.lot_size == source.lot_size
    assert capital.planned_quantity == source.planned_quantity
    assert capital.estimated_premium_outlay == source.estimated_premium_outlay
    assert capital.estimated_risk_amount == source.estimated_maximum_loss
    assert (
        capital.estimated_total_trading_cost
        == source.estimated_total_costs
    )
    assert (
        capital.estimated_total_capital_requirement
        == source.estimated_total_capital_requirement
    )
    assert (
        capital.target_1_lot_count,
        capital.target_2_lot_count,
        capital.target_3_lot_count,
        capital.runner_lot_count,
    ) == (
        source.target_1_lot_count,
        source.target_2_lot_count,
        source.target_3_lot_count,
        source.runner_lot_count,
    )


def test_entry_stop_and_targets_are_exact_task5_authorities():
    source = executable()
    result = adapt_executable_plan_to_paper_lifecycle(source)

    assert result.entry_zone_result is source.entry_result
    assert result.stop_loss_result is source.stop_loss_result
    assert result.three_target_result is source.target_result


def test_trace_chain_is_preserved_in_metadata():
    source = executable()
    result = adapt_executable_plan_to_paper_lifecycle(source)

    assert result.metadata["task4_planning_result_id"] == (
        source.task4_planning_result_id
    )
    assert result.metadata["affordability_result_id"] == (
        source.affordability_result_id
    )
    assert result.metadata["certification_result_id"] == (
        source.certification_result_id
    )
    assert result.metadata["parent_cycle_id"] == source.parent_cycle_id
    assert result.metadata["parent_decision_id"] == source.parent_decision_id
    assert result.metadata["bridge_result_id"] == source.bridge_result_id


def test_result_is_accepted_by_existing_p7_fixture_identity_shape():
    source = executable()
    result = adapt_executable_plan_to_paper_lifecycle(source)
    selected = result.option_contract_selection_result.selected_contract.contract

    assert result.canonical_trade_plan_input.underlying_symbol == (
        selected.underlying_symbol
    )
    assert result.canonical_trade_plan_input.exchange == selected.exchange
    assert result.capital_quantity_result.trade_plan_id == result.integration_id


def test_non_ready_task5_plan_is_rejected():
    source = executable()
    blocked = replace(
        source,
        status="BLOCKED",
        executable=False,
        blockers=("TASK5_BLOCKED",),
    )
    with pytest.raises(ValueError, match="READY"):
        adapt_executable_plan_to_paper_lifecycle(blocked)


def test_wrong_exact_type_is_rejected():
    with pytest.raises(TypeError, match="value"):
        adapt_executable_plan_to_paper_lifecycle(object())


def test_deterministic_and_does_not_mutate_input():
    source = executable()
    before = source.to_json()

    first = adapt_executable_plan_to_paper_lifecycle(source)
    second = adapt_executable_plan_to_paper_lifecycle(source)

    assert first.to_json() == second.to_json()
    assert source.to_json() == before


def test_adapter_has_no_provider_broker_execution_or_persistence_calls():
    source = Path(
        "services/paper_orchestration/"
        "executable_plan_lifecycle_adapter.py"
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
