from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

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
    provider="FYERS",
    *,
    age_seconds=1,
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


def test_quote_supports_all_five_market_exchange_topologies():
    cases = (
        (
            "NIFTY",
            "NSE",
            "UNDERLYING",
        ),
        (
            "NIFTY",
            "NFO",
            "OPTION",
        ),
        (
            "SENSEX",
            "BSE",
            "UNDERLYING",
        ),
        (
            "SENSEX",
            "BFO",
            "FUTURE",
        ),
        (
            "CRUDEOILM",
            "MCX",
            "FUTURE",
        ),
        (
            "GOLDM",
            "MCX",
            "OPTION",
        ),
        (
            "NATGASMINI",
            "MCX",
            "FUTURE",
        ),
    )

    for (
        market,
        exchange,
        instrument_type,
    ) in cases:
        quote = MarketQuoteV2(
            quote_id=(
                f"{market}-quote"
            ),
            market_symbol=market,
            exchange=exchange,
            instrument_type=(
                instrument_type
            ),
            canonical_instrument_id=(
                f"{market}|{instrument_type}"
            ),
            last_price=100.0,
            bid_price=99.9,
            ask_price=100.1,
            volume=1.0,
            open_interest=1.0,
            provenance=provenance(),
        )

        assert (
            quote.market_symbol
            == market
        )


def test_market_exchange_mismatch_fails_closed():
    with pytest.raises(
        ValueError,
        match="exchange mismatch",
    ):
        MarketQuoteV2(
            quote_id="bad",
            market_symbol="NIFTY",
            exchange="MCX",
            instrument_type="OPTION",
            canonical_instrument_id="bad",
            last_price=100.0,
            bid_price=None,
            ask_price=None,
            volume=None,
            open_interest=None,
            provenance=provenance(),
        )


def test_depth_is_sorted_executable_book_without_ltp_field():
    depth = MarketDepthV2(
        depth_id="depth-1",
        market_symbol="NIFTY",
        exchange="NFO",
        instrument_type="OPTION",
        canonical_instrument_id=(
            "NIFTY|OPTION|TEST"
        ),
        bids=(
            MarketDepthLevelV2(
                price=99.95,
                quantity=100,
                orders=2,
            ),
            MarketDepthLevelV2(
                price=99.90,
                quantity=50,
                orders=1,
            ),
        ),
        asks=(
            MarketDepthLevelV2(
                price=100.05,
                quantity=100,
                orders=2,
            ),
            MarketDepthLevelV2(
                price=100.10,
                quantity=50,
                orders=1,
            ),
        ),
        tick_size=0.05,
        provenance=provenance(),
    )

    assert depth.best_bid == 99.95
    assert depth.best_ask == 100.05
    assert not hasattr(
        depth,
        "last_price",
    )


def test_crossed_depth_book_is_rejected():
    with pytest.raises(
        ValueError,
        match="Crossed depth",
    ):
        MarketDepthV2(
            depth_id="bad-depth",
            market_symbol="CRUDEOILM",
            exchange="MCX",
            instrument_type="OPTION",
            canonical_instrument_id=(
                "CRUDE|OPTION|TEST"
            ),
            bids=(
                MarketDepthLevelV2(
                    price=101.0,
                    quantity=1,
                ),
            ),
            asks=(
                MarketDepthLevelV2(
                    price=100.0,
                    quantity=1,
                ),
            ),
            tick_size=0.05,
            provenance=provenance(),
        )


def test_provenance_requires_ordered_aware_timestamps():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        MarketDataProvenanceV2(
            provider="FYERS",
            provider_symbol=None,
            provider_exchange=None,
            source_type="LIVE",
            observed_at=datetime(
                2026,
                9,
                16,
                10,
                0,
            ),
            received_at=NOW,
        )

    with pytest.raises(
        ValueError,
        match="precedes",
    ):
        MarketDataProvenanceV2(
            provider="FYERS",
            provider_symbol=None,
            provider_exchange=None,
            source_type="LIVE",
            observed_at=NOW,
            received_at=(
                NOW
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_candle_contract_carries_completeness_and_provider_provenance():
    candle = MarketCandleV2(
        candle_id="candle-1",
        market_symbol="GOLDM",
        exchange="MCX",
        instrument_type="FUTURE",
        canonical_instrument_id=(
            "GOLDM|FUTURE|TEST"
        ),
        timeframe="5m",
        start_at=NOW,
        end_at=(
            NOW
            + timedelta(
                minutes=5
            )
        ),
        open_price=100.0,
        high_price=102.0,
        low_price=99.0,
        close_price=101.0,
        volume=10,
        is_complete=True,
        provenance=provenance(
            "ANGEL_SMARTAPI"
        ),
    )

    assert candle.is_complete is True
    assert (
        candle.provenance.provider
        == "ANGEL_SMARTAPI"
    )


def test_provider_health_is_sanitized_and_fail_closed():
    healthy = ProviderHealthV2(
        provider="FYERS",
        status="HEALTHY",
        checked_at=NOW,
        last_success_at=NOW,
        consecutive_failures=0,
    )

    assert healthy.status == "HEALTHY"

    unavailable = ProviderHealthV2(
        provider="ANGEL_SMARTAPI",
        status="UNAVAILABLE",
        checked_at=NOW,
        last_success_at=(
            NOW
            - timedelta(
                minutes=1
            )
        ),
        consecutive_failures=2,
        reason_code="RATE_LIMIT",
    )

    assert (
        unavailable.reason_code
        == "RATE_LIMIT"
    )

    with pytest.raises(
        ValueError,
        match="failure evidence",
    ):
        ProviderHealthV2(
            provider="FYERS",
            status="UNAVAILABLE",
            checked_at=NOW,
            last_success_at=None,
            consecutive_failures=0,
            reason_code="NETWORK",
        )
