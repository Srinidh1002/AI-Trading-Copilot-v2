from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
    normalize_full_market_data,
    normalize_history,
    normalize_ltp_data,
    normalize_option_chain,
)


def test_quote_normalizes_to_ltp_data_shape() -> None:
    response = {
        "s": "ok",
        "code": 200,
        "d": [
            {
                "n": "NSE:NIFTY26SEPFUT",
                "v": {
                    "symbol": "NSE:NIFTY26SEPFUT",
                    "lp": 23398.1,
                    "bid": 23397.5,
                    "ask": 23398.5,
                    "volume": 12345,
                    "tt": 1790000000,
                    "fyToken": "101",
                    "prev_close_price": 23380.0,
                },
            }
        ],
    }

    result = normalize_ltp_data(
        response,
        provider_symbol="NSE:NIFTY26SEPFUT",
        exchange="NFO",
        tradingsymbol="NIFTY26SEPFUT",
        symboltoken="999",
    )

    assert result["status"] is True
    assert result["data"]["ltp"] == 23398.1
    assert result["data"]["bid"] == 23397.5
    assert result["data"]["ask"] == 23398.5
    assert result["data"]["volume"] == 12345.0
    assert result["data"]["exchange_timestamp"] == 1790000000
    assert result["data"]["close"] == 23380.0
    assert result["data"]["previous_close"] == 23380.0
    assert result["data"]["previous_close_source"] == "prev_close_price"


def test_quote_derives_previous_close_only_from_provider_change() -> None:
    response = {
        "s": "ok",
        "code": 200,
        "d": [
            {
                "n": "NSE:TCS-EQ",
                "v": {
                    "symbol": "NSE:TCS-EQ",
                    "lp": 3050.0,
                    "ch": 25.0,
                    "volume": 1000,
                },
            }
        ],
    }

    result = normalize_ltp_data(
        response,
        provider_symbol="NSE:TCS-EQ",
        exchange="NSE",
        tradingsymbol="TCS-EQ",
        symboltoken="11536",
    )

    assert result["data"]["close"] == 3025.0
    assert result["data"]["previous_close"] == 3025.0
    assert result["data"]["previous_close_source"] == "DERIVED_FROM_PROVIDER_CHANGE"


def test_quote_fails_closed_on_provider_error() -> None:
    with pytest.raises(
        FyersResponseNormalizationError
    ):
        normalize_ltp_data(
            {
                "s": "error",
                "code": -1,
                "d": [],
            },
            provider_symbol="NSE:NIFTY26SEPFUT",
            exchange="NFO",
            tradingsymbol="NIFTY26SEPFUT",
            symboltoken="999",
        )


def test_history_preserves_fyers_candle_values() -> None:
    response = {
        "s": "ok",
        "candles": [
            [
                1790000000,
                100.0,
                105.0,
                99.0,
                103.0,
                1000,
            ],
            [
                1790000300,
                103.0,
                106.0,
                102.0,
                104.0,
                2000,
            ],
        ],
    }

    result = normalize_history(
        response
    )

    assert result == {
        "status": True,
        "data": response["candles"],
    }


def test_history_preserves_appended_oi_field() -> None:
    response = {
        "s": "ok",
        "candles": [
            [
                1790000000,
                100.0,
                105.0,
                99.0,
                103.0,
                1000,
                50000,
            ]
        ],
    }

    result = normalize_history(
        response
    )

    assert len(
        result["data"][0]
    ) == 7

    assert (
        result["data"][0][6]
        == 50000
    )


def test_depth_normalizes_to_full_market_data_shape() -> None:
    response = {
        "s": "ok",
        "d": {
            "NSE:NIFTY26SEPFUT": {
                "ltp": 23398.1,
                "oi": 510000,
                "v": 12500,
                "o": 23350.0,
                "h": 23425.0,
                "l": 23310.0,
                "c": 23380.0,
                "bids": [
                    {
                        "price": 23398.0,
                        "volume": 50,
                        "ord": 2,
                    }
                ],
                "ask": [
                    {
                        "price": 23398.5,
                        "volume": 75,
                        "ord": 3,
                    }
                ],
            }
        },
    }

    result = normalize_full_market_data(
        response,
        provider_symbol="NSE:NIFTY26SEPFUT",
        symboltoken="999",
    )

    fetched = result[
        "data"
    ][
        "fetched"
    ][0]

    assert fetched[
        "symbolToken"
    ] == "999"

    assert fetched[
        "ltp"
    ] == 23398.1

    assert fetched[
        "opnInterest"
    ] == 510000

    assert fetched[
        "tradeVolume"
    ] == 12500

    assert fetched[
        "depth"
    ][
        "buy"
    ][0][
        "price"
    ] == 23398.0

    assert fetched[
        "depth"
    ][
        "sell"
    ][0][
        "price"
    ] == 23398.5


def test_option_chain_normalizes_ce_and_pe_rows() -> None:
    response = {
        "s": "ok",
        "data": {
            "optionsChain": [
                {
                    "symbol": "NSE:NIFTY2692223300CE",
                    "strike_price": 23300,
                    "option_type": "CE",
                    "ltp": 161.0,
                    "oi": 6615830,
                    "oich": 2225530,
                    "prev_oi": 4390300,
                    "volume": 139193275,
                    "bid": 161.6,
                    "ask": 162.0,
                    "fyToken": "101126092256985",
                    "expiry": 1790000000,
                },
                {
                    "symbol": "NSE:NIFTY2692223300PE",
                    "strike_price": 23300,
                    "option_type": "PE",
                    "ltp": 95.55,
                    "oi": 10868260,
                    "oich": 7669610,
                    "prev_oi": 4390300,
                    "volume": 110302985,
                    "bid": 95.0,
                    "ask": 95.05,
                    "fyToken": "101126092256994",
                    "expiry": 1790000000,
                },
            ]
        },
    }

    rows = normalize_option_chain(
        response
    )

    assert len(rows) == 2

    assert rows[0][
        "type"
    ] == "CE"

    assert rows[0][
        "strike"
    ] == 23300.0

    assert rows[0][
        "oi"
    ] == 6615830

    assert rows[0][
        "bid"
    ] == 161.6

    assert rows[1][
        "type"
    ] == "PE"


def test_normalizer_module_has_no_network_or_broker_imports() -> None:
    path = Path(
        "services/broker/fyers_response_normalizer_v2.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            imports.append(
                node.module
            )

    forbidden_prefixes = (
        "fyers_apiv3",
        "SmartApi",
        "requests",
        "urllib",
        "socket",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
    )

    assert not any(
        module.startswith(
            forbidden_prefixes
        )
        for module in imports
    )


def test_depth_ltt_is_preserved_as_execution_timestamp() -> None:
    response = {
        "s": "ok",
        "d": {
            "MCX:CRUDEOILM26OCT8600CE": {
                "ltp": 512.6,
                "ltt": 1790087132,
                "bids": [
                    {
                        "price": 510.75,
                        "volume": 1,
                        "ord": 1,
                    }
                ],
                "ask": [
                    {
                        "price": 512.4,
                        "volume": 4,
                        "ord": 2,
                    }
                ],
            }
        },
    }

    result = normalize_full_market_data(
        response,
        provider_symbol=("MCX:CRUDEOILM26OCT8600CE"),
        symboltoken=("MCX:CRUDEOILM26OCT8600CE"),
    )

    row = result["data"]["fetched"][0]

    assert row["exchange_timestamp"] == 1790087132

    assert row["timestamp"] == 1790087132

    # Generic FYERS normalization must continue to preserve provider
    # quantity as-is. MCX product conversion belongs to the MCX boundary.
    assert row["bestFiveBuyData"][0]["quantity"] == 1

    assert row["bestFiveSellData"][0]["quantity"] == 4
