"""Task 4 Slice 2 capital and risk authority certification."""
from datetime import datetime, timezone
import ast
from pathlib import Path

import pytest

from services.contracts.capital_risk_authority_v1 import (
    CapitalRiskAuthorityInputV1,
    CapitalRiskAuthorityResultV1,
    ExistingPositionExposureV1,
)
from services.trade_planning.capital_risk_authority import (
    evaluate_capital_risk_authority,
)


NOW = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)


def make_input(**changes):
    values = dict(
        authority_input_id="capital-input-1",
        selected_market=("NIFTY", "NSE"),
        evaluated_at=NOW,
        available_capital=100_000.0,
        risk_percentage=0.02,
        maximum_daily_loss=3_000.0,
        realized_daily_loss=500.0,
        existing_positions=(),
        instrument_lot_size=25,
        premium=100.0,
        bid_price=99.5,
        ask_price=100.5,
        minimum_traded_quantity=1_000,
        observed_traded_quantity=10_000,
        slippage_allowance_fraction=0.02,
        estimated_costs_per_lot=50.0,
    )
    values.update(changes)
    return CapitalRiskAuthorityInputV1(**values)


def evaluate(value):
    return evaluate_capital_risk_authority(
        authority_result_id="capital-result-1",
        authority_input=value,
    )


def test_ready_budget_is_deterministic_and_never_exceeds_capital():
    result = evaluate(make_input())

    assert type(result) is CapitalRiskAuthorityResultV1
    assert result.status == "READY"
    assert result.planning_allowed is True
    assert result.reserved_capital == 0.0
    assert result.deployable_capital == 100_000.0
    assert result.capital_risk_budget == 2_000.0
    assert result.daily_loss_remaining == 2_500.0
    assert result.maximum_new_loss == 2_000.0
    assert result.estimated_one_lot_capital == pytest.approx(
        100.5 * 1.02 * 25 + 50.0
    )
    assert (
        result.maximum_affordable_lots
        * result.estimated_one_lot_capital
        <= result.deployable_capital
    )


def test_existing_positions_reduce_deployable_capital_and_daily_risk():
    existing = (
        ExistingPositionExposureV1(
            position_id="position-1",
            underlying_symbol="SENSEX",
            exchange="BSE",
            reserved_capital=40_000.0,
            maximum_open_loss=1_000.0,
            unrealized_loss=200.0,
        ),
    )
    result = evaluate(make_input(existing_positions=existing))

    assert result.reserved_capital == 40_000.0
    assert result.deployable_capital == 60_000.0
    assert result.existing_open_risk == 1_000.0
    assert result.daily_loss_remaining == 1_500.0
    assert result.maximum_new_loss == 1_500.0


def test_daily_loss_exhaustion_blocks_new_planning():
    existing = (
        ExistingPositionExposureV1(
            position_id="position-1",
            underlying_symbol="NIFTY",
            exchange="NSE",
            reserved_capital=10_000.0,
            maximum_open_loss=2_500.0,
        ),
    )
    result = evaluate(
        make_input(
            maximum_daily_loss=3_000.0,
            realized_daily_loss=500.0,
            existing_positions=existing,
        )
    )

    assert result.status == "BLOCKED"
    assert result.planning_allowed is False
    assert result.maximum_new_loss == 0.0
    assert "MAXIMUM_DAILY_LOSS_EXHAUSTED" in result.blockers


def test_insufficient_capital_for_one_lot_blocks():
    result = evaluate(
        make_input(
            available_capital=2_000.0,
            maximum_daily_loss=1_000.0,
            realized_daily_loss=0.0,
            risk_percentage=0.02,
            instrument_lot_size=25,
            premium=100.0,
            bid_price=99.0,
            ask_price=101.0,
            slippage_allowance_fraction=0.02,
        )
    )

    assert result.maximum_affordable_lots == 0
    assert "CAPITAL_INSUFFICIENT_FOR_ONE_LOT" in result.blockers


def test_liquidity_and_spread_fail_closed():
    result = evaluate(
        make_input(
            minimum_traded_quantity=10_000,
            observed_traded_quantity=500,
            bid_price=95.0,
            premium=100.0,
            ask_price=105.0,
            slippage_allowance_fraction=0.02,
        )
    )

    assert result.status == "BLOCKED"
    assert "INSUFFICIENT_LIQUIDITY" in result.blockers
    assert "SPREAD_EXCEEDS_ALLOWANCE" in result.blockers


def test_input_rejects_invalid_risk_and_position_overcommitment():
    with pytest.raises(ValueError, match="fraction"):
        make_input(risk_percentage=2.0)
    with pytest.raises(ValueError, match="maximum_open_loss"):
        ExistingPositionExposureV1(
            position_id="bad",
            underlying_symbol="NIFTY",
            exchange="NSE",
            reserved_capital=1_000.0,
            maximum_open_loss=2_000.0,
        )


def test_duplicate_positions_are_rejected():
    position = ExistingPositionExposureV1(
        position_id="duplicate",
        underlying_symbol="NIFTY",
        exchange="NSE",
        reserved_capital=1_000.0,
        maximum_open_loss=500.0,
    )
    with pytest.raises(ValueError, match="duplicate"):
        make_input(existing_positions=(position, position))


def test_authority_has_no_p6_option_selection_or_execution_dependencies():
    source = Path(
        "services/trade_planning/capital_risk_authority.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "p6_planning_stage",
        "option_contract_selector",
        "entry_zone",
        "stop_loss",
        "three_target",
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "random.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "time.sleep(",
    ):
        assert token not in source
