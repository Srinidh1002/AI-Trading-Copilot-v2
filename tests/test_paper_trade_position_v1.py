from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.contracts import PaperTradeFillV1, PaperTradePositionV1


OPENED_AT = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def make_entry_fill(**overrides):
    values = {
        "fill_id": "fill-1",
        "trade_plan_id": "plan-1",
        "integrated_trade_plan_result_id": "integrated-1",
        "position_id": "position-1",
        "observation_id": "obs-1",
        "selected_option_contract_id": "contract-1",
        "fill_type": "ENTRY",
        "fill_reason": "ENTRY_ACTIVATED",
        "side": "BUY",
        "filled_lot_count": 4,
        "lot_size": 25,
        "filled_quantity": 100,
        "fill_price": 100.0,
        "gross_notional": 10000.0,
        "estimated_trading_cost": 50.0,
        "net_cash_effect": -10050.0,
        "filled_at": OPENED_AT,
        "source": "TEST",
    }
    values.update(overrides)
    return PaperTradeFillV1(**values)


def make_position(**overrides):
    fill = overrides.pop("entry_fill", make_entry_fill())
    values = {
        "position_id": "position-1",
        "trade_plan_id": "plan-1",
        "integrated_trade_plan_result_id": "integrated-1",
        "lifecycle_policy_id": "policy-1",
        "lifecycle_state_id": "state-open-1",
        "selected_option_contract_id": "contract-1",
        "market": "NIFTY",
        "underlying_symbol": "NIFTY",
        "option_symbol": "NIFTY26JAN24000CE",
        "direction": "BULLISH",
        "option_type": "CALL",
        "strike": 24000.0,
        "expiry": "2026-01-29",
        "entry_fill": fill,
        "entry_price": 100.0,
        "opened_at": OPENED_AT,
        "initial_lot_count": 4,
        "lot_size": 25,
        "initial_quantity": 100,
        "remaining_lot_count": 4,
        "remaining_quantity": 100,
        "target_1_lot_count": 1,
        "target_2_lot_count": 1,
        "target_3_lot_count": 1,
        "runner_lot_count": 1,
        "stop_loss": 80.0,
        "target_1": 110.0,
        "target_2": 120.0,
        "target_3": 130.0,
        "estimated_premium_outlay": 10000.0,
        "estimated_risk_amount": 2000.0,
        "estimated_total_trading_cost": 50.0,
        "estimated_total_capital_requirement": 10050.0,
    }
    values.update(overrides)
    return PaperTradePositionV1(**values)


@pytest.mark.parametrize(
    ("market", "underlying", "option_symbol", "option_type"),
    (
        ("NIFTY", "NIFTY", "NIFTY26JAN24000CE", "CALL"),
        ("NIFTY", "NIFTY", "NIFTY26JAN24000PE", "PUT"),
        ("SENSEX", "SENSEX", "SENSEX26JAN80000CE", "CALL"),
    ),
)
def test_valid_open_positions_for_supported_underlyings(
    market, underlying, option_symbol, option_type
):
    position = make_position(
        market=market,
        underlying_symbol=underlying,
        option_symbol=option_symbol,
        option_type=option_type,
    )
    assert position.lifecycle_state == "OPEN"
    assert position.remaining_quantity == position.initial_quantity


@pytest.mark.parametrize(
    "allocation",
    (
        (0, 0, 0, 0),
        (1, 1, 1, 1),
        (2, 1, 1, 0),
        (0, 2, 1, 1),
    ),
)
def test_valid_allocation_shapes(allocation):
    position = make_position(
        target_1_lot_count=allocation[0],
        target_2_lot_count=allocation[1],
        target_3_lot_count=allocation[2],
        runner_lot_count=allocation[3],
    )
    assert (
        position.target_1_lot_count
        + position.target_2_lot_count
        + position.target_3_lot_count
        + position.runner_lot_count
    ) in (0, position.initial_lot_count)


def test_open_position_copies_risk_cost_and_starts_with_zero_pnl():
    position = make_position()
    assert position.estimated_premium_outlay == 10000.0
    assert position.estimated_risk_amount == 2000.0
    assert position.estimated_total_trading_cost == 50.0
    assert position.estimated_total_capital_requirement == 10050.0
    assert (
        position.realized_gross_pnl,
        position.realized_net_pnl,
        position.unrealized_pnl,
        position.total_pnl,
    ) == (0.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("field_name", "fill_override"),
    (
        ("position_id", {"position_id": "other"}),
        ("trade_plan_id", {"trade_plan_id": "other"}),
        ("integrated_trade_plan_result_id", {"integrated_trade_plan_result_id": "other"}),
        ("selected_option_contract_id", {"selected_option_contract_id": "other"}),
    ),
)
def test_position_identity_must_match_entry_fill(field_name, fill_override):
    with pytest.raises(ValueError):
        make_position(**{field_name: "position-value"}, entry_fill=make_entry_fill(**fill_override))


@pytest.mark.parametrize(
    "fill_override",
    (
        {"fill_type": "EXIT", "fill_reason": "STOP", "side": "SELL", "net_cash_effect": 9950.0},
        {"fill_reason": "STOP"},
        {"side": "SELL"},
    ),
)
def test_position_requires_entry_buy_fill(fill_override):
    with pytest.raises((TypeError, ValueError)):
        make_position(entry_fill=make_entry_fill(**fill_override))


def test_entry_price_must_match_fill_price():
    with pytest.raises(ValueError):
        make_position(entry_price=99.0)


def test_opened_at_must_match_fill_timestamp():
    with pytest.raises(ValueError):
        make_position(opened_at=datetime(2026, 1, 8, 9, 31, tzinfo=timezone.utc))


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("initial_lot_count", 0),
        ("initial_lot_count", -1),
        ("initial_lot_count", True),
        ("lot_size", 0),
        ("lot_size", True),
        ("initial_quantity", 99),
        ("remaining_lot_count", 3),
        ("remaining_quantity", 75),
    ),
)
def test_open_sizing_invariants(field_name, bad_value):
    with pytest.raises((TypeError, ValueError)):
        make_position(**{field_name: bad_value})


def test_entry_fill_sizing_must_match_position():
    with pytest.raises(ValueError):
        make_position(entry_fill=make_entry_fill(filled_lot_count=3, filled_quantity=75, gross_notional=7500.0, net_cash_effect=-7550.0))


def test_allocation_must_be_zero_or_equal_initial_lots():
    with pytest.raises(ValueError):
        make_position(
            target_1_lot_count=1,
            target_2_lot_count=1,
            target_3_lot_count=0,
            runner_lot_count=0,
        )


def test_exit_fills_are_prohibited_for_new_wp2_open_position():
    exit_fill = PaperTradeFillV1(
        "exit-1",
        "plan-1",
        "integrated-1",
        "position-1",
        "obs-2",
        "contract-1",
        "EXIT",
        "STOP",
        "SELL",
        1,
        25,
        25,
        80.0,
        2000.0,
        10.0,
        1990.0,
        OPENED_AT,
        "TEST",
    )
    with pytest.raises(ValueError):
        make_position(exit_fills=(exit_fill,))


@pytest.mark.parametrize(
    "field_name",
    (
        "realized_gross_pnl",
        "realized_net_pnl",
        "unrealized_pnl",
        "total_pnl",
    ),
)
def test_new_open_position_pnl_must_be_zero(field_name):
    with pytest.raises(ValueError):
        make_position(**{field_name: 1.0})


@pytest.mark.parametrize(
    "overrides",
    (
        {"stop_loss": 110.0},
        {"target_1": 80.0},
        {"target_2": 105.0},
        {"target_3": 115.0},
        {"target_1": float("nan")},
    ),
)
def test_stop_and_targets_must_be_finite_and_ordered(overrides):
    with pytest.raises(ValueError):
        make_position(**overrides)


def test_total_capital_requirement_cannot_be_below_outlay_plus_cost():
    with pytest.raises(ValueError):
        make_position(estimated_total_capital_requirement=10049.0)


def test_open_position_must_not_have_blockers():
    with pytest.raises(ValueError):
        make_position(blockers=("BLOCKED",))


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("lifecycle_state", "PARTIALLY_EXITED"),
        ("execution_mode", "LIVE"),
        ("live_execution_eligible", True),
        ("schema_version", "2.0"),
    ),
)
def test_open_state_and_paper_safety_are_strict(field_name, bad_value):
    with pytest.raises(ValueError):
        make_position(**{field_name: bad_value})


def test_serialization_is_deterministic_and_detached():
    metadata = {"nested": {"values": [1, 2]}}
    position = make_position(metadata=metadata, warnings=("PRICE_WARNING",))
    metadata["nested"]["values"].append(3)

    assert position.to_json() == position.to_json()
    assert position.to_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    serialized = position.to_dict()
    serialized["metadata"]["nested"]["values"].append(99)
    serialized["entry_fill"]["metadata"]["changed"] = True
    assert position.to_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    assert "changed" not in position.entry_fill.to_dict()["metadata"]

    semantic = position.semantic_dict()
    assert "position_id" not in semantic
    assert "opened_at" not in semantic
    assert semantic["initial_lot_count"] == 4


def test_position_is_frozen():
    position = make_position()
    with pytest.raises(FrozenInstanceError):
        position.remaining_lot_count = 3
