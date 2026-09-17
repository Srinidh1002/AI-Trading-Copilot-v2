"""Angel SmartAPI read-only SHADOW observation adapter for provider parity.

This module never participates in primary routing and never exposes fallback or
order capability. Exact Angel identities must be supplied by the caller.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence

from services.broker.provider_shadow_parity_v2 import (
    AngelShadowIdentityV2,
    ProviderShadowParityError,
)


class AngelShadowDataProviderV2:
    data_only = True
    role = "SHADOW"
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self, client) -> None:
        if client is None:
            raise ValueError("client is required")
        self._client = client

    @staticmethod
    def _exact_fetched(response: Mapping[str, Any], identity: AngelShadowIdentityV2) -> Mapping[str, Any]:
        if not isinstance(response, Mapping):
            raise ProviderShadowParityError("Angel shadow response invalid")
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise ProviderShadowParityError("Angel shadow response data missing")
        fetched = data.get("fetched")
        if not isinstance(fetched, list):
            raise ProviderShadowParityError("Angel shadow fetched rows missing")
        matches = []
        for row in fetched:
            if not isinstance(row, Mapping):
                continue
            exchange = str(row.get("exchange") or "").strip().upper()
            token = str(row.get("symbolToken") or row.get("symboltoken") or "").strip()
            if exchange == identity.exchange.strip().upper() and token == identity.symboltoken.strip():
                matches.append(row)
        if len(matches) != 1:
            raise ProviderShadowParityError("Angel shadow identity did not match exactly one row")
        return matches[0]

    @staticmethod
    def _side_price(row: Mapping[str, Any], side: str) -> object:
        depth = row.get("depth")
        if not isinstance(depth, Mapping):
            return None
        values = depth.get(side)
        if not isinstance(values, list) or not values:
            return None
        first = values[0]
        if not isinstance(first, Mapping):
            return None
        return first.get("price")

    def get_quote(self, identity: AngelShadowIdentityV2) -> Mapping[str, Any]:
        response = self._client.get_ltp(identity.exchange, identity.tradingsymbol, identity.symboltoken)
        if not isinstance(response, Mapping) or response.get("status") is not True:
            raise ProviderShadowParityError("Angel shadow LTP failed")
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise ProviderShadowParityError("Angel shadow LTP data missing")
        try:
            ltp = float(data["ltp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderShadowParityError("Angel shadow LTP invalid") from exc
        if ltp <= 0:
            raise ProviderShadowParityError("Angel shadow LTP non-positive")
        return {
            "provider": "ANGEL_SMARTAPI",
            "market_symbol": identity.market_symbol.upper(),
            "provider_symbol": str(data.get("tradingsymbol") or identity.tradingsymbol),
            "provider_token": str(data.get("symboltoken") or identity.symboltoken),
            "last_price": ltp,
            "data_only": True,
            "live_execution_eligible": False,
        }

    def get_depth(self, identity: AngelShadowIdentityV2) -> Mapping[str, Any]:
        response = self._client.get_market_data(
            "FULL",
            {identity.exchange.strip().upper(): [identity.symboltoken.strip()]},
        )
        row = self._exact_fetched(response, identity)
        return {
            "provider": "ANGEL_SMARTAPI",
            "market_symbol": identity.market_symbol.upper(),
            "provider_symbol": str(row.get("tradingSymbol") or row.get("tradingsymbol") or identity.tradingsymbol),
            "provider_token": identity.symboltoken,
            "last_price": row.get("ltp"),
            "bid_price": self._side_price(row, "buy") or row.get("bestFiveBuyData"),
            "ask_price": self._side_price(row, "sell") or row.get("bestFiveSellData"),
            "open_interest": row.get("oi", row.get("opnInterest")),
            "volume": row.get("volume", row.get("tradeVolume")),
            "provider_timestamp": row.get("exchange_timestamp", row.get("exchangeTimestamp")),
            "data_only": True,
            "live_execution_eligible": False,
        }

    def get_candles(
        self,
        identity: AngelShadowIdentityV2,
        *,
        interval: str,
        fromdate: str,
        todate: str,
    ) -> tuple[Mapping[str, Any], ...]:
        response = self._client.get_historical_data(
            identity.exchange,
            identity.symboltoken,
            interval,
            fromdate,
            todate,
        )
        rows = response.get("data") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise ProviderShadowParityError("Angel shadow historical rows missing")
        normalized = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                raise ProviderShadowParityError("Angel shadow candle invalid")
            normalized.append({
                "provider": "ANGEL_SMARTAPI",
                "market_symbol": identity.market_symbol.upper(),
                "timestamp": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            })
        return tuple(normalized)

    def get_option_rows(self, identities: Sequence[AngelShadowIdentityV2]) -> tuple[Mapping[str, Any], ...]:
        identities = tuple(identities)
        if not identities:
            raise ValueError("identities cannot be empty")
        by_exchange: dict[str, list[str]] = defaultdict(list)
        by_key = {}
        for identity in identities:
            exchange = identity.exchange.strip().upper()
            token = identity.symboltoken.strip()
            by_exchange[exchange].append(token)
            by_key[(exchange, token)] = identity
        response = self._client.get_market_data("FULL", dict(by_exchange))
        data = response.get("data") if isinstance(response, Mapping) else None
        fetched = data.get("fetched") if isinstance(data, Mapping) else None
        if not isinstance(fetched, list):
            raise ProviderShadowParityError("Angel shadow option rows missing")
        normalized = []
        for row in fetched:
            if not isinstance(row, Mapping):
                continue
            exchange = str(row.get("exchange") or "").strip().upper()
            token = str(row.get("symbolToken") or row.get("symboltoken") or "").strip()
            identity = by_key.get((exchange, token))
            if identity is None:
                continue
            symbol = str(row.get("tradingSymbol") or row.get("tradingsymbol") or identity.tradingsymbol)
            option_type = "CE" if symbol.upper().endswith("CE") else "PE" if symbol.upper().endswith("PE") else ""
            normalized.append({
                "provider": "ANGEL_SMARTAPI",
                "market_symbol": identity.market_symbol.upper(),
                "provider_symbol": symbol,
                "provider_token": token,
                "expiry": row.get("expiry"),
                "strike": row.get("strikePrice", row.get("strike")),
                "option_type": option_type,
                "ltp": row.get("ltp"),
                "bid": self._side_price(row, "buy"),
                "ask": self._side_price(row, "sell"),
                "oi": row.get("oi", row.get("opnInterest")),
                "volume": row.get("volume", row.get("tradeVolume")),
            })
        if len(normalized) != len(identities):
            raise ProviderShadowParityError("Angel shadow option batch incomplete")
        return tuple(normalized)
