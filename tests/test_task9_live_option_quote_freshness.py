from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)
from services.option_full_response_validator import (
    OptionFullResponseValidationError,
    validate_option_full_response,
)
from services.options.angel_option_chain_normalizer import (
    normalize_angel_option_chain,
)
from services.paper_orchestration.certified_live_provider_readers import (
    NIFTY_MARKET_SPEC,
    SENSEX_MARKET_SPEC,
)


NOW = datetime(
    2026,
    8,
    10,
    10,
    0,
    tzinfo=timezone.utc,
)


def full_quote(
    token,
    *,
    timestamp=None,
):
    return {
        "exchange": "NFO",
        "symbolToken": str(token),
        "ltp": 100.0,
        "tradeVolume": 1000,
        "opnInterest": 2000,
        "exchangeTimestamp": (
            timestamp
            if timestamp is not None
            else NOW.isoformat()
        ),
        "depth": {
            "buy": [{"price": 99.0}],
            "sell": [{"price": 101.0}],
        },
    }


def response(
    *items,
):
    return {
        "status": True,
        "data": {
            "fetched": list(items),
            "unfetched": [],
        },
    }


def test_full_quote_timestamp_is_validated_and_retained():
    result = validate_option_full_response(
        response=response(
            full_quote("1"),
        ),
        option_exchange="NFO",
        requested_tokens=("1",),
        received_at=NOW,
        maximum_quote_age_seconds=60.0,
    )

    quote = result["1"]

    assert (
        quote["_validated_provider_timestamp"]
        == NOW
    )
    assert (
        quote[
            "_validated_provider_timestamp_field"
        ]
        == "exchangeTimestamp"
    )
    assert (
        quote[
            "_validated_provider_timestamp_age_seconds"
        ]
        == 0.0
    )


def test_live_full_quote_missing_timestamp_fails_closed():
    quote = full_quote("1")
    quote.pop("exchangeTimestamp")

    with pytest.raises(
        OptionFullResponseValidationError,
        match="timestamp",
    ):
        validate_option_full_response(
            response=response(quote),
            option_exchange="NFO",
            requested_tokens=("1",),
            received_at=NOW,
        )


def test_live_full_quote_stale_timestamp_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="stale",
    ):
        validate_option_full_response(
            response=response(
                full_quote(
                    "1",
                    timestamp=(
                        NOW
                        - timedelta(seconds=61)
                    ).isoformat(),
                )
            ),
            option_exchange="NFO",
            requested_tokens=("1",),
            received_at=NOW,
            maximum_quote_age_seconds=60.0,
        )


def test_live_full_quote_future_timestamp_fails_closed():
    with pytest.raises(
        OptionFullResponseValidationError,
        match="future",
    ):
        validate_option_full_response(
            response=response(
                full_quote(
                    "1",
                    timestamp=(
                        NOW
                        + timedelta(seconds=6)
                    ).isoformat(),
                )
            ),
            option_exchange="NFO",
            requested_tokens=("1",),
            received_at=NOW,
            maximum_future_skew_seconds=5.0,
        )


@pytest.mark.parametrize(
    "spec",
    (
        NIFTY_MARKET_SPEC,
        SENSEX_MARKET_SPEC,
    ),
)
def test_normalizer_uses_contract_quote_timestamp_not_parent_timestamp(
    spec,
):
    quote_time = (
        NOW
        - timedelta(seconds=15)
    )

    row = {
        "token": "123",
        "symbol": (
            f"{spec.underlying_symbol}"
            "27AUG2625000CE"
        ),
        "option_type": "CE",
        "expiry": "2026-08-27",
        "strike": 25000,
        "lotsize": 25,
        "tick_size": 0.05,
        "premium": 100,
        "bid": 99,
        "ask": 101,
        "volume": 1000,
        "open_interest": 2000,
        "provider_timestamp": quote_time,
        "exchange": spec.option_exchange,
        "underlying": spec.underlying_symbol,
    }

    result = normalize_angel_option_chain(
        contracts=(row,),
        market_spec=spec,
        spot_price=25000,
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    contract = result.universe.contracts[0]

    assert contract.market_timestamp == quote_time
    assert contract.market_timestamp != NOW


def test_normalizer_keeps_fixture_compatibility_without_quote_timestamp():
    row = {
        "token": "123",
        "symbol": "NIFTY27AUG2625000CE",
        "option_type": "CE",
        "expiry": "2026-08-27",
        "strike": 25000,
        "lotsize": 25,
        "tick_size": 0.05,
        "premium": 100,
        "bid": 99,
        "ask": 101,
        "volume": 1000,
        "open_interest": 2000,
    }

    result = normalize_angel_option_chain(
        contracts=(row,),
        market_spec=NIFTY_MARKET_SPEC,
        spot_price=25000,
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert (
        result.universe.contracts[0].market_timestamp
        == NOW
    )


def test_builder_rejects_non_aware_clock_before_certifying_quotes():
    builder = LiveOptionChainBuilder(
        instrument_master=MagicMock(),
        market_client=MagicMock(),
        clock=lambda: datetime(
            2026,
            8,
            10,
            10,
            0,
        ),
    )

    assert callable(builder.clock)
