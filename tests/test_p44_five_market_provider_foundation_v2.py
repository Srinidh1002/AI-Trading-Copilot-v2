from pathlib import Path

import pytest

from services.broker.provider_data_interfaces_v2 import (
    HistoricalDataProviderV2,
    InstrumentResolverV2,
    QuoteDepthProviderV2,
    StreamingMarketDataProviderV2,
)
from services.contracts.trading_market_v2 import (
    TradingMarketV2,
)
from services.core.five_market_universe_v2 import (
    TARGET_FIVE_MARKET_IDENTITIES,
    TARGET_FIVE_MARKET_SYMBOLS,
    TARGET_FIVE_MARKET_UNIVERSE,
    get_target_market,
    is_target_market,
    normalize_target_market_symbol,
)
from services.core.market_universe import (
    CANONICAL_MARKET_IDENTITIES,
)


EXPECTED_TARGET_IDENTITIES = (
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
    ("CRUDEOILM", "MCX"),
    ("GOLDM", "MCX"),
    ("SILVERM", "MCX"),
)


def test_five_market_universe_is_exact_and_paper_only():
    assert TARGET_FIVE_MARKET_IDENTITIES == (
        EXPECTED_TARGET_IDENTITIES
    )

    assert TARGET_FIVE_MARKET_SYMBOLS == (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )

    assert (
        TARGET_FIVE_MARKET_UNIVERSE.execution_mode
        == "PAPER"
    )

    assert (
        TARGET_FIVE_MARKET_UNIVERSE.live_execution_eligible
        is False
    )


def test_exchange_topology_separates_index_derivatives_from_mcx():
    nifty = get_target_market(
        "NIFTY",
        "NSE",
    )
    sensex = get_target_market(
        "SENSEX",
        "BSE",
    )
    crude = get_target_market(
        "CRUDEOILM",
        "MCX",
    )

    assert nifty.market_type == "INDEX"
    assert nifty.derivative_exchange == "NFO"

    assert sensex.market_type == "INDEX"
    assert sensex.derivative_exchange == "BFO"

    assert crude.market_type == "COMMODITY"
    assert crude.derivative_exchange == "MCX"


def test_alias_resolution_is_provider_independent():
    assert (
        normalize_target_market_symbol(
            "nifty 50"
        )
        == "NIFTY"
    )

    assert (
        normalize_target_market_symbol(
            "crude oil mini"
        )
        == "CRUDEOILM"
    )

    assert (
        normalize_target_market_symbol(
            "silver mini"
        )
        == "SILVERM"
    )

    assert is_target_market(
        "gold mini",
        "MCX",
    )

    assert not is_target_market(
        "BANKNIFTY",
        "NSE",
    )


def test_exchange_mismatch_and_unknown_market_fail_closed():
    with pytest.raises(
        ValueError,
        match="exchange mismatch",
    ):
        get_target_market(
            "NIFTY",
            "BSE",
        )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        get_target_market(
            "UNKNOWN",
        )


def test_market_contract_rejects_invalid_exchange_topology():
    with pytest.raises(
        ValueError,
        match="index exchange topology",
    ):
        TradingMarketV2(
            symbol="TESTINDEX",
            display_name="Test Index",
            market_type="INDEX",
            underlying_exchange="NSE",
            derivative_exchange="MCX",
            aliases=(
                "TEST INDEX",
            ),
        )

    with pytest.raises(
        ValueError,
        match="commodity exchange topology",
    ):
        TradingMarketV2(
            symbol="TESTCOM",
            display_name="Test Commodity",
            market_type="COMMODITY",
            underlying_exchange="NSE",
            derivative_exchange="NFO",
            aliases=(
                "TEST COMMODITY",
            ),
        )


def test_v1_index_universe_remains_unchanged():
    assert CANONICAL_MARKET_IDENTITIES == (
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    )


def test_v2_does_not_promote_provisional_contract_metadata():
    commodity = get_target_market(
        "GOLDM",
        "MCX",
    )

    assert not hasattr(
        commodity,
        "tick_size",
    )
    assert not hasattr(
        commodity,
        "lot_size",
    )
    assert not hasattr(
        commodity,
        "strike_interval",
    )


def test_provider_capabilities_are_separate_protocols():
    assert {
        "resolve",
    }.issubset(
        InstrumentResolverV2.__dict__
    )

    assert {
        "get_candles",
    }.issubset(
        HistoricalDataProviderV2.__dict__
    )

    assert {
        "get_quote",
        "get_depth",
    }.issubset(
        QuoteDepthProviderV2.__dict__
    )

    assert {
        "subscribe",
        "unsubscribe",
        "close",
    }.issubset(
        StreamingMarketDataProviderV2.__dict__
    )


def test_new_foundation_contains_no_provider_implementation():
    paths = (
        Path(
            "services/contracts/"
            "trading_market_v2.py"
        ),
        Path(
            "services/contracts/"
            "trading_universe_v2.py"
        ),
        Path(
            "services/core/"
            "five_market_universe_v2.py"
        ),
        Path(
            "services/broker/"
            "provider_data_interfaces_v2.py"
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
        "FYERS_CLIENT_ID",
        "place_order",
        "placeOrder(",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
