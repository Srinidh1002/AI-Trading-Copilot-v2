from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.market_session import (
    MarketSessionPolicy,
    validate_session_timestamp,
)


IST = ZoneInfo("Asia/Kolkata")
REGULAR = datetime(
    2026,
    7,
    27,
    10,
    0,
    tzinfo=IST,
)


def validate(
    *,
    market_timestamp=REGULAR,
    evaluated_at=REGULAR,
    validation_mode="LENIENT_ANALYSIS",
    policy=None,
):
    return validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=market_timestamp,
        evaluated_at=evaluated_at,
        validation_mode=validation_mode,
        policy=policy,
        id_factory=lambda: "validation",
    )


def test_regular_session_is_deterministic():
    result = validate()

    assert result.session_state == "REGULAR"
    assert result.session_phase == "REGULAR_TRADING"
    assert result.analysis_allowed is True
    assert result.paper_execution_allowed is True
    assert result.timestamp_age_seconds == 0
    assert result.stale is False
    assert result.future_timestamp is False
    assert (
        result.semantic_dict()
        == result.semantic_dict()
    )


def test_snapshot_at_maximum_age_is_accepted():
    result = validate(
        evaluated_at=(
            REGULAR
            + timedelta(seconds=300)
        )
    )

    assert result.stale is False
    assert result.analysis_allowed is True


def test_snapshot_beyond_maximum_age_fails_closed():
    result = validate(
        evaluated_at=(
            REGULAR
            + timedelta(seconds=301)
        )
    )

    assert result.stale is True
    assert result.analysis_allowed is False
    assert result.paper_execution_allowed is False
    assert (
        "Market timestamp is stale."
        in result.blockers
    )


def test_future_timestamp_at_tolerance_is_accepted():
    result = validate(
        market_timestamp=(
            REGULAR
            + timedelta(seconds=5)
        )
    )

    assert result.future_timestamp is False
    assert result.analysis_allowed is True


def test_future_timestamp_beyond_tolerance_fails_closed():
    result = validate(
        market_timestamp=(
            REGULAR
            + timedelta(seconds=6)
        )
    )

    assert result.future_timestamp is True
    assert result.analysis_allowed is False
    assert (
        "Market timestamp exceeds allowed future skew."
        in result.blockers
    )


@pytest.mark.parametrize(
    "validation_mode",
    [
        "",
        "UNKNOWN",
        None,
        1,
    ],
)
def test_unsupported_validation_mode_is_rejected(
    validation_mode,
):
    with pytest.raises(
        ValueError,
        match="validation_mode",
    ):
        validate(
            validation_mode=validation_mode,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "max_snapshot_age_seconds": -1,
        },
        {
            "max_future_skew_seconds": -1,
        },
        {
            "max_snapshot_age_seconds": float(
                "inf"
            ),
        },
        {
            "pre_open_start": time(9, 16),
            "regular_open": time(9, 15),
        },
    ],
)
def test_invalid_policy_is_rejected(kwargs):
    with pytest.raises(ValueError):
        MarketSessionPolicy(**kwargs)


def test_policy_type_is_enforced():
    with pytest.raises(
        TypeError,
        match="MarketSessionPolicy",
    ):
        validate(
            policy=object(),
        )


def test_naive_market_timestamp_is_rejected():
    with pytest.raises(
        ValueError,
        match="market_timestamp",
    ):
        validate(
            market_timestamp=REGULAR.replace(
                tzinfo=None
            ),
        )


def test_naive_evaluated_at_is_rejected():
    with pytest.raises(
        ValueError,
        match="evaluated_at",
    ):
        validate(
            evaluated_at=REGULAR.replace(
                tzinfo=None
            ),
        )


def test_metadata_is_normalized_and_defensive():
    result = validate()

    assert result.metadata == {
        "calendar_source": "EMPTY",
        "new_entry_cutoff": "15:20",
        "regular_close": "15:40",
        "regular_new_entry_window_open": True,
        "validation_mode": "LENIENT_ANALYSIS",
    }

    with pytest.raises(
        TypeError,
        match="does not support item assignment",
    ):
        result.metadata[
            "validation_mode"
        ] = "CHANGED"
