from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.external_context_policy_v1 import ExternalContextPolicyV1
from services.contracts.external_market_observation_v1 import (
    ExternalMarketObservationV1,
)
from services.external_context import evaluate_global_market_context


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def observation(
    name: str = "SP500",
    direction: str = "POSITIVE",
    status: str = "READY",
    **overrides,
) -> ExternalMarketObservationV1:
    if name == "GIFT_NIFTY":
        observation_type = "PREMARKET_INDICATOR"
        market_region = "INDIA"
        asset_class = "EQUITY_INDEX_FUTURE"
    elif name in {"BRENT_CRUDE", "WTI_CRUDE"}:
        observation_type = "COMMODITY"
        market_region = "GLOBAL"
        asset_class = "COMMODITY"
    else:
        observation_type = "INDEX_CLOSE"
        market_region = "UNITED_STATES"
        asset_class = "EQUITY_INDEX"

    values = {
        "external_market_observation_id": name,
        "created_at": NOW,
        "canonical_name": name,
        "observation_type": observation_type,
        "market_region": market_region,
        "asset_class": asset_class,
        "source_id": "S",
        "source_timestamp": NOW,
        "session_reference": "PREVIOUS_SESSION_CLOSE",
        "current_value": 101.0,
        "previous_value": 100.0,
        "change_value": 1.0,
        "change_percent": 1.0,
        "direction": direction,
        "observation_status": status,
    }
    values.update(overrides)

    return ExternalMarketObservationV1(**values)


def run(
    observations: tuple[ExternalMarketObservationV1, ...],
    **overrides,
):
    return evaluate_global_market_context(
        underlying_symbol="NIFTY",
        exchange="NSE",
        observations=observations,
        created_at=NOW,
        result_id="r",
        **overrides,
    )


def test_gift_and_us_alignment():
    result = run(
        (
            observation("GIFT_NIFTY"),
            observation("SP500"),
        )
    )

    assert result.aggregate_direction == "POSITIVE"


def test_conflicting_observations_are_not_false_consensus():
    result = run(
        (
            observation("GIFT_NIFTY"),
            observation("SP500", direction="NEGATIVE"),
        )
    )

    assert result.context_status == "CONFLICTING"


def test_required_missing_blocks_and_stale_optional_warns():
    policy = ExternalContextPolicyV1(
        required_observation_names={
            ("NIFTY", "NSE"): ("SP500",),
        },
        optional_observation_names={},
        minimum_available_global_observations=0,
        minimum_global_confirmation_count=0,
    )

    missing_result = run((), policy=policy)

    assert missing_result.context_status == "BLOCKED"
    assert missing_result.available_observation_count == 0
    assert missing_result.blockers

    stale = observation(
        source_timestamp=NOW - timedelta(seconds=901),
    )

    stale_result = run((stale,))

    assert stale_result.context_status == "UNAVAILABLE"
    assert stale_result.aggregate_direction == "UNAVAILABLE"
    assert stale_result.available_observation_count == 0
    assert stale_result.unavailable_observation_count == 1
    assert any("STALE" in warning for warning in stale_result.warnings)


def test_programmer_errors_raise():
    with pytest.raises(TypeError):
        run([observation()])

    with pytest.raises(ValueError):
        evaluate_global_market_context(
            underlying_symbol="NIFTY",
            exchange="BSE",
            observations=(),
            created_at=NOW,
            result_id="r",
        )