from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from services.market_session import (
    validate_session_timestamp,
)


IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    "hour,minute,state",
    (
        (8, 59, "CLOSED"),
        (9, 0, "PRE_OPEN"),
        (9, 10, "PRE_OPEN"),
        (9, 14, "PRE_OPEN"),
        (9, 15, "REGULAR"),
        (10, 0, "REGULAR"),
        (15, 20, "REGULAR"),
        (15, 21, "REGULAR"),
        (15, 39, "REGULAR"),
        (15, 40, "REGULAR"),
        (15, 41, "POST_CLOSE"),
    ),
)
def test_nifty_boundaries(
    hour,
    minute,
    state,
):
    value = datetime(
        2026,
        7,
        27,
        hour,
        minute,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=value,
        evaluated_at=value,
    )

    assert result.session_state == state
