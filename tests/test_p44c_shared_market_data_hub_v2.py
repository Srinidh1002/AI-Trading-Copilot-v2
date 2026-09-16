from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from services.broker.shared_market_data_hub_v2 import (
    IncompleteMarketDataError,
    MarketDataUnavailableError,
    SharedMarketDataHubV2,
    StaleMarketDataError,
)
from services.contracts.market_data_v2 import (
    MarketCandleV2,
    MarketDataProvenanceV2,
    MarketDepthLevelV2,
    MarketDepthV2,
    MarketQuoteV2,
    ProviderHealthV2,
)


NOW = datetime(
    2026,
    9,
    16,
    10,
    0,
    tzinfo=timezone.utc,
)


def provenance(
    provider,
    age_seconds,
):
    observed = NOW - timedelta(
        seconds=age_seconds
    )

    return MarketDataProvenanceV2(
        provider=provider,
        provider_symbol="TEST",
        provider_exchange="TEST",
        source_type="TEST",
        observed_at=observed,
        received_at=observed,
    )


def quote(
    provider,
    price,
    age_seconds,
):
    return MarketQuoteV2(
        quote_id=f"{provider}-q",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING"
        ),
        last_price=price,
        bid_price=price - 0.1,
        ask_price=price + 0.1,
        volume=100,
        open_interest=None,
        provenance=provenance(
            provider,
            age_seconds,
        ),
    )


def depth(
    provider,
    age_seconds=1,
):
    return MarketDepthV2(
        depth_id=f"{provider}-d",
        market_symbol="NIFTY",
        exchange="NFO",
        instrument_type="OPTION",
        canonical_instrument_id=(
            "NIFTY|OPTION|TEST"
        ),
        bids=(
            MarketDepthLevelV2(
                price=99.95,
                quantity=10,
            ),
        ),
        asks=(
            MarketDepthLevelV2(
                price=100.05,
                quantity=10,
            ),
        ),
        tick_size=0.05,
        provenance=provenance(
            provider,
            age_seconds,
        ),
    )


def candle(
    provider,
    *,
    minute,
    complete=True,
):
    start = NOW + timedelta(
        minutes=minute
    )

    return MarketCandleV2(
        candle_id=(
            f"{provider}-{minute}"
        ),
        market_symbol="CRUDEOILM",
        exchange="MCX",
        instrument_type="FUTURE",
        canonical_instrument_id=(
            "CRUDEOILM|FUTURE|TEST"
        ),
        timeframe="5m",
        start_at=start,
        end_at=(
            start
            + timedelta(
                minutes=5
            )
        ),
        open_price=100,
        high_price=102,
        low_price=99,
        close_price=101,
        volume=10,
        is_complete=complete,
        provenance=MarketDataProvenanceV2(
            provider=provider,
            provider_symbol="TEST",
            provider_exchange="MCX",
            source_type="TEST",
            observed_at=start,
            received_at=start,
        ),
    )


def test_hub_keeps_primary_and_shadow_quotes_separate():
    hub = SharedMarketDataHubV2()

    hub.publish_quote(
        quote(
            "FYERS",
            100.0,
            1,
        )
    )

    hub.publish_quote(
        quote(
            "ANGEL_SMARTAPI",
            101.0,
            1,
        )
    )

    fyers = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING"
        ),
        max_age_seconds=10,
        now=NOW,
    )

    angel = hub.get_quote(
        provider="ANGEL_SMARTAPI",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING"
        ),
        max_age_seconds=10,
        now=NOW,
    )

    assert fyers.last_price == 100.0
    assert angel.last_price == 101.0


def test_stale_primary_fails_without_silent_shadow_fallback():
    hub = SharedMarketDataHubV2()

    hub.publish_quote(
        quote(
            "FYERS",
            100.0,
            60,
        )
    )

    hub.publish_quote(
        quote(
            "ANGEL_SMARTAPI",
            101.0,
            1,
        )
    )

    with pytest.raises(
        StaleMarketDataError,
        match="STALE_MARKET_DATA",
    ):
        hub.get_quote(
            provider="FYERS",
            market_symbol="NIFTY",
            exchange="NSE",
            instrument_type="UNDERLYING",
            canonical_instrument_id=(
                "NIFTY|UNDERLYING"
            ),
            max_age_seconds=10,
            now=NOW,
        )

    shadow = hub.get_quote(
        provider="ANGEL_SMARTAPI",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING"
        ),
        max_age_seconds=10,
        now=NOW,
    )

    assert shadow.last_price == 101.0


def test_depth_must_be_explicitly_available():
    hub = SharedMarketDataHubV2()

    hub.publish_quote(
        quote(
            "FYERS",
            100.0,
            1,
        )
    )

    with pytest.raises(
        MarketDataUnavailableError,
        match="DEPTH_UNAVAILABLE",
    ):
        hub.get_depth(
            provider="FYERS",
            market_symbol="NIFTY",
            exchange="NFO",
            instrument_type="OPTION",
            canonical_instrument_id=(
                "NIFTY|OPTION|TEST"
            ),
            max_age_seconds=10,
            now=NOW,
        )

    hub.publish_depth(
        depth("FYERS")
    )

    result = hub.get_depth(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NFO",
        instrument_type="OPTION",
        canonical_instrument_id=(
            "NIFTY|OPTION|TEST"
        ),
        max_age_seconds=10,
        now=NOW,
    )

    assert result.best_bid == 99.95


def test_candle_series_are_provider_scoped_and_require_completeness():
    hub = SharedMarketDataHubV2()

    hub.publish_candle(
        candle(
            "FYERS",
            minute=0,
            complete=True,
        )
    )

    hub.publish_candle(
        candle(
            "FYERS",
            minute=5,
            complete=False,
        )
    )

    hub.publish_candle(
        candle(
            "ANGEL_SMARTAPI",
            minute=0,
            complete=True,
        )
    )

    result = hub.get_candles(
        provider="FYERS",
        market_symbol="CRUDEOILM",
        exchange="MCX",
        instrument_type="FUTURE",
        canonical_instrument_id=(
            "CRUDEOILM|FUTURE|TEST"
        ),
        timeframe="5m",
        count=1,
        require_complete=True,
    )

    assert len(result) == 1
    assert (
        result[0].provenance.provider
        == "FYERS"
    )

    with pytest.raises(
        IncompleteMarketDataError,
        match="INSUFFICIENT_CANDLE_HISTORY",
    ):
        hub.get_candles(
            provider="FYERS",
            market_symbol="CRUDEOILM",
            exchange="MCX",
            instrument_type="FUTURE",
            canonical_instrument_id=(
                "CRUDEOILM|FUTURE|TEST"
            ),
            timeframe="5m",
            count=2,
            require_complete=True,
        )


def test_provider_health_is_explicit_not_inferred():
    hub = SharedMarketDataHubV2()

    with pytest.raises(
        MarketDataUnavailableError,
        match="PROVIDER_HEALTH_UNAVAILABLE",
    ):
        hub.get_provider_health(
            "FYERS"
        )

    health = ProviderHealthV2(
        provider="FYERS",
        status="HEALTHY",
        checked_at=NOW,
        last_success_at=NOW,
        consecutive_failures=0,
    )

    hub.set_provider_health(
        health
    )

    assert (
        hub.get_provider_health(
            "FYERS"
        )
        == health
    )


def test_new_hub_contains_no_provider_sdk_or_order_authority():
    paths = (
        Path(
            "services/contracts/"
            "market_data_v2.py"
        ),
        Path(
            "services/broker/"
            "shared_market_data_hub_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "SmartConnect",
        "fyers_apiv3",
        "yfinance",
        "ANGEL_API_KEY",
        "ANGEL_CLIENT_ID",
        "FYERS_CLIENT_ID",
        "FYERS_SECRET_KEY",
        "place_order",
        "placeOrder(",
        "generateSession",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
