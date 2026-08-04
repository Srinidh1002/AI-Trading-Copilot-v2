from datetime import datetime, timedelta, timezone

import pytest

from services.broader_market_intelligence import (
    evaluate_cross_market_correlation,
)
from services.contracts.broader_market_intelligence_policy_v1 import (
    DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,
)
from services.contracts.market_candle_series_v1 import (
    MarketCandleSeriesV1,
)
from services.contracts.market_candle_v1 import (
    MarketCandleV1,
)
from services.contracts.market_data_provenance_v1 import (
    MarketDataProvenanceV1,
)


NOW = datetime(
    2026,
    1,
    1,
    12,
    tzinfo=timezone.utc,
)


def prices_from_returns(
    start_price,
    returns,
):
    prices = [float(start_price)]

    for return_value in returns:
        prices.append(
            prices[-1] * (1.0 + return_value)
        )

    return tuple(prices)


def series(
    symbol="NIFTY",
    exchange="NSE",
    values=None,
    shift=0,
    complete=True,
):
    values = (
        values
        if values is not None
        else tuple(
            100 + index
            for index in range(31)
        )
    )

    candles = []

    for index, value in enumerate(values):
        start = (
            NOW
            - timedelta(
                minutes=(len(values) - index) * 5
            )
            + timedelta(minutes=shift)
        )

        provenance = MarketDataProvenanceV1(
            "TEST",
            symbol,
            exchange,
            "TEST",
            start,
            start,
            False,
            None,
            None,
        )

        candles.append(
            MarketCandleV1(
                f"{symbol}-{index}",
                symbol,
                exchange,
                "5m",
                start,
                start + timedelta(minutes=5),
                value,
                value,
                value,
                value,
                1,
                complete,
                provenance,
            )
        )

    return MarketCandleSeriesV1(
        f"{symbol}-series",
        symbol,
        exchange,
        "5m",
        tuple(candles),
        None,
        None,
        NOW,
    )


def evaluate(
    primary_values,
    related_values,
    **changes,
):
    return evaluate_cross_market_correlation(
        primary_series=series(
            values=primary_values,
        ),
        related_series=series(
            "SENSEX",
            "BSE",
            related_values,
        ),
        created_at=NOW,
        evidence_id="evidence",
        **changes,
    )


def test_perfect_positive_and_deterministic():
    primary_returns = tuple(
        0.001 + (index * 0.0001)
        for index in range(30)
    )

    related_returns = tuple(
        return_value * 2
        for return_value in primary_returns
    )

    value = evaluate(
        prices_from_returns(
            100,
            primary_returns,
        ),
        prices_from_returns(
            200,
            related_returns,
        ),
    )

    assert value.correlation_value == pytest.approx(1.0)
    assert value.correlation_state == "STRONG_POSITIVE"
    assert value.aligned_sample_size == 30
    assert value.to_json() == value.to_json()


def test_perfect_negative_and_weak_states():
    primary_returns = tuple(
        0.001 + (index * 0.0001)
        for index in range(30)
    )

    negative_returns = tuple(
        -return_value
        for return_value in primary_returns
    )

    negative = evaluate(
        prices_from_returns(
            100,
            primary_returns,
        ),
        prices_from_returns(
            200,
            negative_returns,
        ),
    )

    assert negative.correlation_value == pytest.approx(-1.0)
    assert negative.correlation_state == "STRONG_NEGATIVE"

    weak_related_returns = tuple(
        (
            0.0015
            if index % 4 == 0
            else -0.0007
            if index % 4 == 1
            else 0.0002
            if index % 4 == 2
            else -0.001
        )
        for index in range(30)
    )

    weak = evaluate(
        prices_from_returns(
            100,
            primary_returns,
        ),
        prices_from_returns(
            200,
            weak_related_returns,
        ),
    )

    assert weak.correlation_state == "WEAK"


def test_insufficient_and_zero_variance():
    short = evaluate(
        tuple(
            range(100, 130)
        ),
        tuple(
            range(200, 230)
        ),
    )

    assert (
        short.evidence_status
        == "INSUFFICIENT_DATA"
    )

    flat = evaluate(
        tuple(
            100
            for _ in range(31)
        ),
        tuple(
            200 + index
            for index in range(31)
        ),
    )

    assert flat.evidence_status == "UNAVAILABLE"


def test_wrong_types_and_timeframe_mismatch():
    with pytest.raises(TypeError):
        evaluate_cross_market_correlation(
            primary_series=[],
            related_series=[],
            created_at=NOW,
            evidence_id="x",
        )

    related = series(
        "SENSEX",
        "BSE",
    )

    object.__setattr__(
        related,
        "timeframe",
        "1h",
    )

    result = evaluate_cross_market_correlation(
        primary_series=series(),
        related_series=related,
        created_at=NOW,
        evidence_id="x",
    )

    assert result.evidence_status == "MISALIGNED"


def test_stale_future_and_partial_are_blocked():
    old_primary = series(
        shift=-120,
    )

    stale = evaluate_cross_market_correlation(
        primary_series=old_primary,
        related_series=series(
            "SENSEX",
            "BSE",
        ),
        created_at=NOW,
        evidence_id="x",
    )

    assert stale.evidence_status == "STALE"

    partial = evaluate_cross_market_correlation(
        primary_series=series(
            complete=False,
        ),
        related_series=series(
            "SENSEX",
            "BSE",
        ),
        created_at=NOW,
        evidence_id="x",
    )

    assert partial.evidence_status == "BLOCKED"


def test_default_policy_is_accepted():
    result = evaluate(
        tuple(
            100 + index
            for index in range(31)
        ),
        tuple(
            200 + (index * 2)
            for index in range(31)
        ),
        policy=(
            DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY
        ),
    )

    assert result.primary_symbol == "NIFTY"
    assert result.related_symbol == "SENSEX"