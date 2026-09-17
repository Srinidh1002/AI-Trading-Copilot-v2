from __future__ import annotations

import pytest

from services.broker.angel_shadow_data_v2 import AngelShadowDataProviderV2
from services.broker.provider_shadow_parity_v2 import AngelShadowIdentityV2


IDENTITY = AngelShadowIdentityV2(
    market_symbol="NIFTY",
    exchange="NSE",
    tradingsymbol="Nifty 50",
    symboltoken="99926000",
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_ltp(self, exchange, tradingsymbol, symboltoken):
        self.calls.append(("LTP", exchange, tradingsymbol, symboltoken))
        return {
            "status": True,
            "data": {
                "ltp": 23001.5,
                "tradingsymbol": tradingsymbol,
                "symboltoken": symboltoken,
            },
        }

    def get_market_data(self, mode, exchange_tokens):
        self.calls.append((mode, exchange_tokens))
        tokens = [token for values in exchange_tokens.values() for token in values]
        fetched = []
        for i, token in enumerate(tokens):
            fetched.append(
                {
                    "exchange": "NSE",
                    "symbolToken": token,
                    "tradingSymbol": f"OPT{i}CE",
                    "ltp": 100 + i,
                    "depth": {
                        "buy": [{"price": 99.5 + i}],
                        "sell": [{"price": 100.5 + i}],
                    },
                    "oi": 1000 + i,
                    "volume": 5000 + i,
                    "exchange_timestamp": 1789639200 + i,
                    "strikePrice": 23000 + 50 * i,
                    "expiry": "2026-09-24",
                }
            )
        return {"status": True, "data": {"fetched": fetched, "unfetched": []}}

    def get_historical_data(self, exchange, symboltoken, interval, fromdate, todate):
        self.calls.append(("HIST", exchange, symboltoken, interval, fromdate, todate))
        return {
            "status": True,
            "data": [
                ["2026-09-17T09:15:00+05:30", 100, 102, 99, 101, 1000],
            ],
        }


def test_shadow_quote_normalizes_read_only_flags():
    client = FakeClient()
    provider = AngelShadowDataProviderV2(client)
    quote = provider.get_quote(IDENTITY)
    assert quote["provider"] == "ANGEL_SMARTAPI"
    assert quote["last_price"] == 23001.5
    assert quote["data_only"] is True
    assert quote["live_execution_eligible"] is False
    assert provider.role == "SHADOW"
    assert provider.order_capability_allowed is False
    assert provider.automatic_fallback_allowed is False


def test_shadow_depth_extracts_exact_token_and_depth():
    provider = AngelShadowDataProviderV2(FakeClient())
    depth = provider.get_depth(IDENTITY)
    assert depth["bid_price"] == 99.5
    assert depth["ask_price"] == 100.5
    assert depth["open_interest"] == 1000
    assert depth["volume"] == 5000


def test_shadow_historical_normalizes_angel_rows():
    provider = AngelShadowDataProviderV2(FakeClient())
    rows = provider.get_candles(
        IDENTITY,
        interval="FIVE_MINUTE",
        fromdate="2026-09-17 09:15",
        todate="2026-09-17 09:20",
    )
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-09-17T09:15:00+05:30"
    assert rows[0]["close"] == 101
    assert rows[0]["provider"] == "ANGEL_SMARTAPI"


def test_shadow_option_batch_requires_complete_exact_identity_set():
    client = FakeClient()
    provider = AngelShadowDataProviderV2(client)
    identities = (
        AngelShadowIdentityV2("NIFTY", "NSE", "OPT0CE", "1001"),
        AngelShadowIdentityV2("NIFTY", "NSE", "OPT1CE", "1002"),
    )
    rows = provider.get_option_rows(identities)
    assert len(rows) == 2
    assert rows[0]["provider_token"] == "1001"
    assert rows[0]["bid"] == 99.5
    assert rows[1]["ask"] == 101.5


def test_shadow_depth_fails_on_identity_mismatch():
    class Bad(FakeClient):
        def get_market_data(self, mode, exchange_tokens):
            return {
                "status": True,
                "data": {
                    "fetched": [
                        {"exchange": "NSE", "symbolToken": "DIFFERENT", "ltp": 100}
                    ],
                    "unfetched": [],
                },
            }

    with pytest.raises(Exception):
        AngelShadowDataProviderV2(Bad()).get_depth(IDENTITY)


def test_shadow_option_batch_fails_when_one_contract_missing():
    class Partial(FakeClient):
        def get_market_data(self, mode, exchange_tokens):
            first = next(iter(exchange_tokens.values()))[0]
            return {
                "status": True,
                "data": {
                    "fetched": [
                        {
                            "exchange": "NSE",
                            "symbolToken": first,
                            "tradingSymbol": "ONLYCE",
                            "ltp": 100,
                            "depth": {"buy": [{"price": 99}], "sell": [{"price": 101}]},
                        }
                    ],
                    "unfetched": [],
                },
            }

    identities = (
        AngelShadowIdentityV2("NIFTY", "NSE", "A", "1"),
        AngelShadowIdentityV2("NIFTY", "NSE", "B", "2"),
    )
    with pytest.raises(Exception):
        AngelShadowDataProviderV2(Partial()).get_option_rows(identities)
