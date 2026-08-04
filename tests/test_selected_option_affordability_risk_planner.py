"""Task 3C selected-option affordability and risk planning."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.contracts.capital_risk_authority_v1 import (
    ExistingPositionExposureV1,
)
from services.trade_planning.selected_option_affordability_risk_planner import (
    plan_selected_option_affordability_risk,
)
from test_selected_option_contract_certifier import certify, ready_bridge


def certified(symbol="NIFTY", direction="BULLISH", **changes):
    return certify(ready_bridge(symbol, direction, **changes))


def plan(value, **changes):
    defaults = dict(
        affordability_result_id="affordability-1",
        authority_input_id="authority-input-1",
        authority_result_id="authority-result-1",
        certification=value,
        evaluated_at=value.evaluated_at,
        available_capital=100_000.0,
        risk_percentage=0.02,
        maximum_daily_loss=3_000.0,
        realized_daily_loss=500.0,
        existing_positions=(),
        minimum_traded_quantity=500,
        slippage_allowance_fraction=0.03,
        estimated_costs_per_lot=50.0,
    )
    defaults.update(changes)
    return plan_selected_option_affordability_risk(**defaults)


@pytest.mark.parametrize(
    ("symbol", "direction", "right"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_ready_for_both_markets_and_directions(symbol, direction, right):
    result = plan(certified(symbol, direction))

    assert result.status == "READY"
    assert result.planning_allowed is True
    assert result.selected_market[0] == symbol
    assert result.direction == direction
    assert result.option_right == right
    assert result.premium == 100.0
    assert result.bid_price == 99.0
    assert result.ask_price == 101.0
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_full_task_3a_and_3b_trace_is_preserved():
    certification = certified()
    result = plan(certification)

    assert result.certification_result_id == certification.certification_result_id
    assert result.parent_cycle_id == certification.parent_cycle_id
    assert result.parent_decision_id == certification.parent_decision_id
    assert result.bridge_result_id == certification.bridge_result_id
    assert result.selected_child_result_id == certification.selected_child_result_id
    assert result.candidate_id == certification.candidate_id
    assert result.observation_id == certification.observation_id
    assert result.ranking_result_id == certification.ranking_result_id
    assert result.universe_id == certification.universe_id
    assert result.contract_id == certification.contract_id


def test_one_lot_capital_and_affordability_are_deterministic():
    result = plan(certified())

    expected_one_lot = 101.0 * 1.03 * 25 + 50.0
    assert result.adjusted_entry_premium == pytest.approx(104.03)
    assert result.estimated_one_lot_capital == pytest.approx(expected_one_lot)
    assert result.maximum_affordable_lots == int(100_000.0 // expected_one_lot)
    assert (
        result.maximum_affordable_lots * result.estimated_one_lot_capital
        <= result.deployable_capital
    )


def test_existing_positions_reduce_capital_and_daily_loss_capacity():
    position = ExistingPositionExposureV1(
        position_id="existing-1",
        underlying_symbol="SENSEX",
        exchange="BSE",
        reserved_capital=40_000.0,
        maximum_open_loss=1_000.0,
        unrealized_loss=200.0,
    )
    result = plan(certified(), existing_positions=(position,))

    assert result.reserved_capital == 40_000.0
    assert result.deployable_capital == 60_000.0
    assert result.existing_open_risk == 1_000.0
    assert result.daily_loss_remaining == 1_500.0
    assert result.maximum_new_loss == 1_500.0


def test_insufficient_capital_blocks():
    result = plan(
        certified(),
        available_capital=2_000.0,
        maximum_daily_loss=1_000.0,
        realized_daily_loss=0.0,
    )

    assert result.status == "BLOCKED"
    assert result.planning_allowed is False
    assert result.maximum_affordable_lots == 0
    assert "CAPITAL_INSUFFICIENT_FOR_ONE_LOT" in result.blockers


def test_daily_loss_exhaustion_blocks():
    position = ExistingPositionExposureV1(
        position_id="existing-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        reserved_capital=10_000.0,
        maximum_open_loss=2_500.0,
    )
    result = plan(
        certified(),
        existing_positions=(position,),
        maximum_daily_loss=3_000.0,
        realized_daily_loss=500.0,
    )

    assert result.status == "BLOCKED"
    assert result.maximum_new_loss == 0.0
    assert "MAXIMUM_DAILY_LOSS_EXHAUSTED" in result.blockers


def test_liquidity_failure_blocks():
    result = plan(
        certified(volume=500.0),
        minimum_traded_quantity=501,
    )

    assert result.status == "BLOCKED"
    assert "INSUFFICIENT_LIQUIDITY" in result.blockers


def test_spread_failure_blocks():
    result = plan(
        certified(),
        slippage_allowance_fraction=0.01,
    )

    assert result.status == "BLOCKED"
    assert "SPREAD_EXCEEDS_ALLOWANCE" in result.blockers


@pytest.mark.parametrize("certification_status", ("BLOCKED", "UNAVAILABLE"))
def test_non_certified_task_3b_result_propagates_as_unavailable(
    certification_status,
):
    value = certified()
    blocked = replace(
        value,
        status=certification_status,
        selected_rank=None,
        selected_candidate=None,
        selected_contract=None,
        contract_id=None,
        trading_symbol=None,
        instrument_token=None,
        expiry_date=None,
        strike=None,
        lot_size=None,
        premium=None,
        bid_price=None,
        ask_price=None,
        spread_value=None,
        spread_fraction=None,
        quote_timestamp=None,
        contract_age_seconds=None,
        quote_age_seconds=None,
        liquidity_score=None,
        open_interest=None,
        volume=None,
        blockers=("TASK_3B_BLOCKED",),
    )

    result = plan(blocked)

    assert result.status == "UNAVAILABLE"
    assert result.planning_allowed is False
    assert result.contract_id is None
    assert result.total_capital is None
    assert result.blockers == (
        "OPTION_CONTRACT_NOT_CERTIFIED",
        "TASK_3B_BLOCKED",
    )


def test_certified_contract_evidence_cannot_be_overridden():
    result = plan(
        certified(),
        available_capital=50_000.0,
        estimated_costs_per_lot=100.0,
    )

    assert result.lot_size == 25
    assert result.premium == 100.0
    assert result.bid_price == 99.0
    assert result.ask_price == 101.0
    assert result.total_capital == 50_000.0


def test_duplicate_positions_are_rejected():
    position = ExistingPositionExposureV1(
        position_id="duplicate",
        underlying_symbol="NIFTY",
        exchange="NSE",
        reserved_capital=1_000.0,
        maximum_open_loss=500.0,
    )

    with pytest.raises(ValueError, match="duplicate"):
        plan(certified(), existing_positions=(position, position))


def test_input_is_not_mutated_and_output_is_deterministic():
    certification = certified()
    before = certification.to_json()

    first = plan(certification)
    second = plan(certification)

    assert first.to_json() == second.to_json()
    assert certification.to_json() == before


def test_wrong_certification_type_is_rejected():
    with pytest.raises(TypeError, match="certification"):
        plan_selected_option_affordability_risk(
            affordability_result_id="affordability-1",
            authority_input_id="authority-input-1",
            authority_result_id="authority-result-1",
            certification=object(),
            evaluated_at=certified().evaluated_at,
            available_capital=100_000.0,
            risk_percentage=0.02,
            maximum_daily_loss=3_000.0,
            realized_daily_loss=0.0,
            existing_positions=(),
            minimum_traded_quantity=500,
            slippage_allowance_fraction=0.03,
        )


def test_planner_has_no_provider_broker_lifecycle_or_persistence_dependencies():
    source = Path(
        "services/trade_planning/"
        "selected_option_affordability_risk_planner.py"
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
