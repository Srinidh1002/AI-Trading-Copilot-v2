from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts import PaperMarketObservationV1


NOW = datetime(2026, 1, 8, 9, 20, tzinfo=timezone.utc)


def make_observation(**overrides):
    values = {
        "observation_id": "obs-1",
        "trade_plan_id": "plan-1",
        "integrated_trade_plan_result_id": "integrated-1",
        "selected_option_contract_id": "contract-1",
        "observed_at": NOW,
        "received_at": NOW + timedelta(seconds=1),
        "market_session_date": date(2026, 1, 8),
        "underlying_symbol": "NIFTY",
        "underlying_last_price": 24000.0,
        "option_symbol": "NIFTY26JAN24000CE",
        "option_last_price": 125.0,
        "market": "NIFTY",
        "exchange": "NFO",
        "session_state": "OPEN",
        "is_market_open": True,
        "is_expiry_session": False,
        "data_quality_status": "FRESH",
        "source": "TEST",
    }
    values.update(overrides)
    return PaperMarketObservationV1(**values)


def test_last_price_only_observation_is_valid_and_paper_only():
    observation = make_observation()
    assert observation.option_last_price == 125.0
    assert observation.execution_mode == "PAPER"
    assert observation.live_execution_eligible is False


def test_complete_option_and_underlying_ohlc_and_spread_are_valid():
    observation = make_observation(
        underlying_open=23980.0,
        underlying_high=24020.0,
        underlying_low=23960.0,
        underlying_close=24010.0,
        option_open=120.0,
        option_high=130.0,
        option_low=118.0,
        option_close=127.0,
        bid_price=124.5,
        ask_price=125.5,
    )
    assert observation.option_low <= observation.option_last_price <= observation.option_high
    assert observation.ask_price >= observation.bid_price


@pytest.mark.parametrize(
    "session_state",
    (
        "PRE_OPEN",
        "OPEN",
        "ENTRY_CUTOFF",
        "POSITION_MANAGEMENT",
        "CLOSED",
        "HOLIDAY",
        "UNKNOWN",
    ),
)
def test_every_session_state_is_supported(session_state):
    assert make_observation(session_state=session_state).session_state == session_state


@pytest.mark.parametrize("quality", ("FRESH", "STALE", "PARTIAL", "INVALID"))
def test_every_data_quality_status_is_supported(quality):
    assert make_observation(data_quality_status=quality).data_quality_status == quality


@pytest.mark.parametrize(
    "field_name",
    (
        "observation_id",
        "trade_plan_id",
        "integrated_trade_plan_result_id",
        "selected_option_contract_id",
        "underlying_symbol",
        "option_symbol",
        "market",
        "exchange",
        "source",
    ),
)
def test_blank_identity_or_source_is_rejected(field_name):
    with pytest.raises(ValueError):
        make_observation(**{field_name: "   "})


@pytest.mark.parametrize("field_name", ("observed_at", "received_at"))
def test_naive_timestamps_are_rejected(field_name):
    with pytest.raises(ValueError):
        make_observation(**{field_name: datetime(2026, 1, 8, 9, 20)})


def test_received_timestamp_cannot_precede_observed_timestamp():
    with pytest.raises(ValueError):
        make_observation(received_at=NOW - timedelta(seconds=1))


def test_market_session_date_rejects_datetime_subclass():
    with pytest.raises(TypeError):
        make_observation(market_session_date=NOW)


@pytest.mark.parametrize(
    "field_name",
    (
        "underlying_last_price",
        "option_last_price",
        "underlying_open",
        "underlying_high",
        "underlying_low",
        "underlying_close",
        "option_open",
        "option_high",
        "option_low",
        "option_close",
        "bid_price",
        "ask_price",
    ),
)
@pytest.mark.parametrize("bad_value", (True, -1.0, float("nan"), float("inf"), float("-inf")))
def test_invalid_prices_are_rejected(field_name, bad_value):
    with pytest.raises((TypeError, ValueError)):
        make_observation(**{field_name: bad_value})


@pytest.mark.parametrize("field_name", ("underlying_last_price", "option_last_price"))
def test_required_last_prices_must_be_positive(field_name):
    with pytest.raises(ValueError):
        make_observation(**{field_name: 0.0})


@pytest.mark.parametrize(
    "partial_group",
    (
        {"option_open": 120.0},
        {"option_high": 130.0, "option_low": 118.0},
        {"underlying_open": 23980.0},
        {"underlying_high": 24020.0, "underlying_low": 23960.0},
    ),
)
def test_partial_ohlc_groups_are_rejected(partial_group):
    with pytest.raises(ValueError):
        make_observation(**partial_group)


@pytest.mark.parametrize(
    "overrides",
    (
        {
            "option_open": 120.0,
            "option_high": 118.0,
            "option_low": 130.0,
            "option_close": 125.0,
        },
        {
            "option_open": 131.0,
            "option_high": 130.0,
            "option_low": 118.0,
            "option_close": 125.0,
        },
        {
            "option_open": 120.0,
            "option_high": 130.0,
            "option_low": 118.0,
            "option_close": 117.0,
        },
        {
            "option_open": 120.0,
            "option_high": 124.0,
            "option_low": 118.0,
            "option_close": 123.0,
            "option_last_price": 125.0,
        },
    ),
)
def test_incoherent_option_ohlc_is_rejected(overrides):
    with pytest.raises(ValueError):
        make_observation(**overrides)


@pytest.mark.parametrize(
    "overrides",
    (
        {"bid_price": 124.0},
        {"ask_price": 126.0},
        {"bid_price": 126.0, "ask_price": 125.0},
    ),
)
def test_bid_ask_pair_must_be_complete_and_ordered(overrides):
    with pytest.raises(ValueError):
        make_observation(**overrides)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("session_state", "TRADING"),
        ("data_quality_status", "GOOD"),
        ("is_market_open", 1),
        ("is_expiry_session", 0),
        ("execution_mode", "LIVE"),
        ("live_execution_eligible", True),
        ("schema_version", "2.0"),
    ),
)
def test_controlled_values_and_safety_invariants_are_enforced(field_name, bad_value):
    with pytest.raises((TypeError, ValueError)):
        make_observation(**{field_name: bad_value})


def test_warnings_metadata_and_source_timestamps_are_frozen_and_detached():
    metadata = {"nested": {"items": [1, 2]}}
    source_timestamps = {"quote": NOW}
    observation = make_observation(
        warnings=("PARTIAL_OBSERVATION_USED", "PARTIAL_OBSERVATION_USED"),
        metadata=metadata,
        source_timestamps=source_timestamps,
    )

    metadata["nested"]["items"].append(3)
    source_timestamps["quote"] = NOW + timedelta(days=1)

    assert observation.warnings == ("PARTIAL_OBSERVATION_USED",)
    assert observation.to_dict()["metadata"] == {"nested": {"items": [1, 2]}}
    assert observation.to_dict()["source_timestamps"] == {"quote": NOW.isoformat()}

    serialized = observation.to_dict()
    serialized["metadata"]["nested"]["items"].append(99)
    serialized["warnings"].append("MUTATED")
    assert observation.to_dict()["metadata"] == {"nested": {"items": [1, 2]}}
    assert observation.warnings == ("PARTIAL_OBSERVATION_USED",)


def test_serialization_is_deterministic_and_semantic_dict_excludes_provenance():
    observation = make_observation(
        metadata={"z": 1, "a": {"b": 2}},
        source_timestamps={"quote": NOW},
    )
    first_dict = observation.to_dict()
    assert observation.to_dict() == first_dict
    assert observation.to_json() == observation.to_json()
    semantic = observation.semantic_dict()
    assert "observation_id" not in semantic
    assert "observed_at" not in semantic
    assert "received_at" not in semantic
    assert "source_timestamps" not in semantic
    assert semantic["option_last_price"] == 125.0


def test_dataclass_is_frozen():
    observation = make_observation()
    with pytest.raises(FrozenInstanceError):
        observation.option_last_price = 130.0
