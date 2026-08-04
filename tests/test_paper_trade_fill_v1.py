from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts import PaperTradeFillV1


FILLED_AT = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def make_fill(**overrides):
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
        "filled_lot_count": 2,
        "lot_size": 25,
        "filled_quantity": 50,
        "fill_price": 10.0,
        "gross_notional": 500.0,
        "estimated_trading_cost": 5.0,
        "net_cash_effect": -505.0,
        "filled_at": FILLED_AT,
        "source": "TEST",
    }
    values.update(overrides)
    return PaperTradeFillV1(**values)


def make_exit(reason, *, target_name=None, cost=5.0, **overrides):
    values = {
        "fill_type": "EXIT",
        "fill_reason": reason,
        "side": "SELL",
        "target_name": target_name,
        "estimated_trading_cost": cost,
        "net_cash_effect": 500.0 - cost,
    }
    values.update(overrides)
    return make_fill(**values)


def test_buy_entry_fill_math_and_cash_effect():
    fill = make_fill()
    assert fill.filled_quantity == fill.filled_lot_count * fill.lot_size
    assert fill.gross_notional == fill.filled_quantity * fill.fill_price
    assert fill.net_cash_effect == -(fill.gross_notional + fill.estimated_trading_cost)


@pytest.mark.parametrize(
    ("reason", "target_name"),
    (
        ("TARGET_1", "T1"),
        ("TARGET_2", "T2"),
        ("TARGET_3", "T3"),
        ("STOP", None),
        ("INVALIDATION", None),
        ("SESSION_CLOSE", None),
        ("EXPIRY_CLOSE", None),
        ("CANCELLED", None),
        ("RUNNER_CLOSE", None),
    ),
)
def test_valid_sell_exit_reasons(reason, target_name):
    fill = make_exit(reason, target_name=target_name)
    assert fill.side == "SELL"
    assert fill.net_cash_effect == 495.0


@pytest.mark.parametrize("cost", (0.0, 5.0))
def test_zero_and_nonzero_costs_are_supported(cost):
    fill = make_fill(
        estimated_trading_cost=cost,
        net_cash_effect=-(500.0 + cost),
    )
    assert fill.estimated_trading_cost == cost


@pytest.mark.parametrize(
    "field_name",
    (
        "fill_id",
        "trade_plan_id",
        "integrated_trade_plan_result_id",
        "position_id",
        "observation_id",
        "selected_option_contract_id",
        "source",
    ),
)
def test_blank_identifiers_are_rejected(field_name):
    with pytest.raises(ValueError):
        make_fill(**{field_name: " "})


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("fill_type", "ORDER"),
        ("fill_reason", "PROFIT"),
        ("side", "LONG"),
    ),
)
def test_unknown_controlled_values_are_rejected(field_name, bad_value):
    with pytest.raises(ValueError):
        make_fill(**{field_name: bad_value})


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("filled_lot_count", 0),
        ("filled_lot_count", -1),
        ("filled_lot_count", True),
        ("lot_size", 0),
        ("lot_size", -1),
        ("lot_size", True),
        ("filled_quantity", 0),
        ("filled_quantity", True),
    ),
)
def test_lot_and_quantity_values_are_strict_positive_integers(field_name, bad_value):
    with pytest.raises((TypeError, ValueError)):
        make_fill(**{field_name: bad_value})


def test_quantity_mismatch_is_rejected():
    with pytest.raises(ValueError):
        make_fill(filled_quantity=49)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("fill_price", 0.0),
        ("fill_price", -1.0),
        ("fill_price", True),
        ("fill_price", float("nan")),
        ("fill_price", float("inf")),
        ("gross_notional", 0.0),
        ("gross_notional", -1.0),
        ("gross_notional", float("nan")),
        ("estimated_trading_cost", -1.0),
        ("estimated_trading_cost", True),
        ("estimated_trading_cost", float("inf")),
        ("net_cash_effect", True),
        ("net_cash_effect", float("nan")),
    ),
)
def test_invalid_money_values_are_rejected(field_name, bad_value):
    with pytest.raises((TypeError, ValueError)):
        make_fill(**{field_name: bad_value})


def test_gross_notional_mismatch_is_rejected():
    with pytest.raises(ValueError):
        make_fill(gross_notional=499.0)


def test_entry_cash_effect_mismatch_is_rejected():
    with pytest.raises(ValueError):
        make_fill(net_cash_effect=-500.0)


def test_exit_cash_effect_mismatch_is_rejected():
    with pytest.raises(ValueError):
        make_exit("STOP", net_cash_effect=500.0)


@pytest.mark.parametrize(
    "overrides",
    (
        {"side": "SELL"},
        {"fill_reason": "STOP"},
        {"target_name": "T1"},
    ),
)
def test_entry_semantics_are_strict(overrides):
    with pytest.raises(ValueError):
        make_fill(**overrides)


@pytest.mark.parametrize(
    "overrides",
    (
        {"fill_type": "EXIT", "side": "BUY", "fill_reason": "STOP", "net_cash_effect": -505.0},
        {"fill_type": "EXIT", "side": "SELL", "fill_reason": "ENTRY_ACTIVATED", "net_cash_effect": 495.0},
        {"fill_type": "EXIT", "side": "SELL", "fill_reason": "TARGET_1", "target_name": None, "net_cash_effect": 495.0},
        {"fill_type": "EXIT", "side": "SELL", "fill_reason": "TARGET_2", "target_name": "T1", "net_cash_effect": 495.0},
        {"fill_type": "EXIT", "side": "SELL", "fill_reason": "STOP", "target_name": "T1", "net_cash_effect": 495.0},
    ),
)
def test_exit_semantics_are_strict(overrides):
    with pytest.raises(ValueError):
        make_fill(**overrides)


def test_naive_filled_at_is_rejected():
    with pytest.raises(ValueError):
        make_fill(filled_at=datetime(2026, 1, 8, 9, 30))


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("execution_mode", "LIVE"),
        ("live_execution_eligible", True),
        ("schema_version", "2.0"),
    ),
)
def test_paper_safety_invariants_are_enforced(field_name, bad_value):
    with pytest.raises(ValueError):
        make_fill(**{field_name: bad_value})


def test_warnings_metadata_and_timestamps_are_frozen_and_detached():
    metadata = {"nested": {"values": [1, 2]}}
    timestamps = {"quote": FILLED_AT}
    fill = make_fill(
        warnings=("ENTRY_PRICE_DIFFERS_FROM_P6_PREMIUM",) * 2,
        source_timestamps=timestamps,
        metadata=metadata,
    )

    metadata["nested"]["values"].append(3)
    timestamps["quote"] = FILLED_AT + timedelta(days=1)

    assert fill.warnings == ("ENTRY_PRICE_DIFFERS_FROM_P6_PREMIUM",)
    assert fill.to_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    assert fill.to_dict()["source_timestamps"] == {"quote": FILLED_AT.isoformat()}

    serialized = fill.to_dict()
    serialized["metadata"]["nested"]["values"].append(99)
    serialized["warnings"].append("MUTATED")
    assert fill.to_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    assert fill.warnings == ("ENTRY_PRICE_DIFFERS_FROM_P6_PREMIUM",)


def test_serialization_is_deterministic_and_semantic_dict_excludes_provenance():
    fill = make_fill(metadata={"z": 1, "a": {"b": 2}})
    assert fill.to_json() == fill.to_json()
    assert fill.to_dict() == fill.to_dict()
    semantic = fill.semantic_dict()
    assert "fill_id" not in semantic
    assert "filled_at" not in semantic
    assert "source_timestamps" not in semantic
    assert semantic["gross_notional"] == 500.0


def test_dataclass_is_frozen():
    fill = make_fill()
    with pytest.raises(FrozenInstanceError):
        fill.fill_price = 11.0
