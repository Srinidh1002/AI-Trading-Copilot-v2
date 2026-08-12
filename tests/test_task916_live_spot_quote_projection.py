from datetime import datetime, timedelta, timezone

import pytest

from services.certification.task9_live_spot_quote_projection import (
    evaluate_task9_live_spot_quote_quality,
    project_task9_live_spot_quote,
    project_task9_live_spot_quote_with_quality,
)
from services.contracts.market_data_quality_result_v1 import (
    MarketDataQualityResultV1,
)
from services.contracts.market_quote_v1 import (
    MarketQuoteV1,
)
from services.market.angel_live_observation_normalizer import (
    AngelLiveSpotObservationV1,
)


def _spot(
    *,
    symbol="NIFTY",
    exchange="NSE",
    token="99926000",
    option_exchange="NFO",
    price=25000.0,
    provider_timestamp=None,
    evaluated_at=None,
    blockers=(),
    warnings=(),
):
    observed = (
        provider_timestamp
        or datetime(
            2026,
            8,
            10,
            4,
            0,
            tzinfo=timezone.utc,
        )
    )

    received = (
        evaluated_at
        or observed + timedelta(seconds=2)
    )

    return AngelLiveSpotObservationV1(
        underlying_symbol=symbol,
        exchange=exchange,
        symboltoken=token,
        option_exchange=option_exchange,
        price=price,
        provider_timestamp=observed,
        evaluated_at=received,
        blockers=blockers,
        warnings=warnings,
    )


def test_projects_exact_nifty_spot_without_provider_read():
    spot = _spot()

    quote = project_task9_live_spot_quote(
        spot=spot,
    )

    assert type(quote) is MarketQuoteV1

    assert (
        quote.underlying_symbol,
        quote.exchange,
    ) == (
        "NIFTY",
        "NSE",
    )

    assert quote.observed_at is spot.provider_timestamp
    assert quote.received_at is spot.evaluated_at
    assert quote.last_price == spot.price

    assert quote.previous_close is None
    assert quote.open_price is None
    assert quote.high_price is None
    assert quote.low_price is None
    assert quote.volume is None
    assert quote.bid_price is None
    assert quote.ask_price is None

    assert quote.provenance.provider == "ANGEL_ONE"
    assert quote.provenance.source_type == "LIVE"
    assert quote.provenance.is_cached is False
    assert quote.execution_mode == "PAPER"
    assert quote.live_execution_eligible is False


def test_projects_exact_sensex_identity():
    spot = _spot(
        symbol="SENSEX",
        exchange="BSE",
        token="99919000",
        option_exchange="BFO",
        price=81000.0,
    )

    quote = project_task9_live_spot_quote(
        spot=spot,
    )

    assert (
        quote.underlying_symbol,
        quote.exchange,
    ) == (
        "SENSEX",
        "BSE",
    )

    assert quote.last_price == 81000.0


def test_quote_quality_uses_same_receipt_boundary():
    spot = _spot()

    quote = project_task9_live_spot_quote(
        spot=spot,
    )

    quality = (
        evaluate_task9_live_spot_quote_quality(
            quote=quote,
        )
    )

    assert (
        type(quality)
        is MarketDataQualityResultV1
    )

    assert quality.subject_type == "QUOTE"
    assert quality.quality_status == "VALID"

    assert quality.observed_at == quote.observed_at
    assert quality.received_at == quote.received_at

    assert quality.age_seconds == pytest.approx(
        (
            quote.received_at
            - quote.observed_at
        ).total_seconds()
    )

    assert quality.underlying_symbol == "NIFTY"
    assert quality.exchange == "NSE"


def test_combined_projection_is_deterministic():
    spot = _spot()

    quote1, quality1 = (
        project_task9_live_spot_quote_with_quality(
            spot=spot,
        )
    )

    quote2, quality2 = (
        project_task9_live_spot_quote_with_quality(
            spot=spot,
        )
    )

    assert quote1.to_dict() == quote2.to_dict()
    assert (
        quality1.quality_result_id
        == quality2.quality_result_id
    )
    assert (
        quality1.quality_status
        == quality2.quality_status
    )


def test_missing_price_fails_closed():
    observed = datetime(
        2026,
        8,
        10,
        4,
        0,
        tzinfo=timezone.utc,
    )

    spot = AngelLiveSpotObservationV1(
        underlying_symbol="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
        option_exchange="NFO",
        price=None,
        provider_timestamp=observed,
        evaluated_at=(
            observed + timedelta(seconds=1)
        ),
        blockers=("SPOT_UNAVAILABLE",),
    )

    with pytest.raises(
        ValueError,
        match="available spot price",
    ):
        project_task9_live_spot_quote(
            spot=spot,
        )


def test_missing_provider_timestamp_fails_closed():
    observed = datetime(
        2026,
        8,
        10,
        4,
        0,
        tzinfo=timezone.utc,
    )

    spot = AngelLiveSpotObservationV1(
        underlying_symbol="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
        option_exchange="NFO",
        price=None,
        provider_timestamp=None,
        evaluated_at=observed,
        blockers=(
            "SPOT_PROVIDER_TIMESTAMP_MISSING",
        ),
    )

    with pytest.raises(
        ValueError,
        match="available spot price",
    ):
        project_task9_live_spot_quote(
            spot=spot,
        )