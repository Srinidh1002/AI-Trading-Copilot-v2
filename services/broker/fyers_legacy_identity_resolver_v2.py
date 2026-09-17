"""Translate existing Angel-shaped market identities into FYERS symbols.

F12 uses this only as a compatibility seam for the existing UnifiedTradingBot
readers. It performs no authentication, network I/O, order action or fallback.
Unknown/ambiguous identities fail closed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class FyersLegacyIdentityResolutionError(RuntimeError):
    """Existing Angel-shaped identity cannot be mapped safely to FYERS."""


def _text(value: object) -> str:
    return str(value or "").strip()


def _upper(value: object) -> str:
    return _text(value).upper()


class FyersLegacyIdentityResolverV2:
    """Resolve exchange/trading-symbol/token triples into FYERS symbols."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        instrument_rows: Sequence[Mapping[str, Any]],
        resolver,
        clock=None,
    ) -> None:
        if resolver is None or not hasattr(resolver, "resolve"):
            raise ValueError("resolver with resolve() is required")
        if not isinstance(instrument_rows, Sequence) or isinstance(
            instrument_rows, (str, bytes)
        ):
            raise TypeError("instrument_rows must be a sequence")

        self._resolver = resolver
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._by_exchange_token: dict[tuple[str, str], Mapping[str, Any]] = {}

        for row in instrument_rows:
            if not isinstance(row, Mapping):
                continue
            exchange = _upper(row.get("exch_seg") or row.get("exchange"))
            token = _text(
                row.get("token")
                or row.get("symboltoken")
                or row.get("symbolToken")
            )
            if not exchange or not token:
                continue
            key = (exchange, token)
            if key in self._by_exchange_token:
                raise FyersLegacyIdentityResolutionError(
                    f"AMBIGUOUS_LEGACY_IDENTITY:{exchange}:{token}"
                )
            self._by_exchange_token[key] = row

    def _resolved_symbol(self, **kwargs) -> str:
        result = self._resolver.resolve(**kwargs)
        if not isinstance(result, Mapping):
            raise FyersLegacyIdentityResolutionError("FYERS_RESOLUTION_INVALID")
        symbol = result.get("provider_symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise FyersLegacyIdentityResolutionError("FYERS_SYMBOL_MISSING")
        return symbol.strip()

    def _row_for(self, exchange: str, token: str) -> Mapping[str, Any] | None:
        return self._by_exchange_token.get((exchange, token))

    def __call__(
        self,
        exchange: str,
        tradingsymbol: str | None,
        symboltoken: str,
    ) -> str:
        exchange = _upper(exchange)
        token = _text(symboltoken)
        trading = _text(tradingsymbol)
        if not exchange or not token:
            raise FyersLegacyIdentityResolutionError("LEGACY_IDENTITY_INCOMPLETE")

        row = self._row_for(exchange, token)
        row_symbol = _text(
            (row or {}).get("symbol")
            or (row or {}).get("tradingsymbol")
            or (row or {}).get("tradingSymbol")
        )
        row_name = _upper((row or {}).get("name"))
        symbol_upper = _upper(trading or row_symbol)
        instrument_type = _upper(
            (row or {}).get("instrumenttype")
            or (row or {}).get("instrument_type")
        )

        # Canonical index underlyings. The legacy bot historically uses token
        # "1" for SENSEX candle reads, while newer evidence may expose
        # 99919000. Recognize both only on the BSE index boundary.
        if exchange == "NSE" and (
            token == "99926000"
            or symbol_upper in {"NIFTY", "NIFTY 50"}
            or row_name in {"NIFTY", "NIFTY 50"}
        ):
            return self._resolved_symbol(
                market_symbol="NIFTY",
                instrument_type="UNDERLYING",
                as_of=self._clock(),
            )

        if exchange == "BSE" and (
            token in {"1", "99919000"}
            or symbol_upper in {"SENSEX", "BSE SENSEX", "S&P BSE SENSEX"}
            or row_name in {"SENSEX", "BSE SENSEX", "S&P BSE SENSEX"}
        ):
            return self._resolved_symbol(
                market_symbol="SENSEX",
                instrument_type="UNDERLYING",
                as_of=self._clock(),
            )

        if exchange == "NSE" and (
            "INDIA VIX" in symbol_upper
            or "INDIAVIX" in symbol_upper
            or "INDIA VIX" in row_name
            or "INDIAVIX" in row_name
        ):
            return "NSE:INDIAVIX-INDEX"

        # Cash equities used by weighted-constituent analysis.
        if exchange == "NSE" and (trading.endswith("-EQ") or row_symbol.endswith("-EQ")):
            symbol = trading or row_symbol
            if not symbol:
                raise FyersLegacyIdentityResolutionError("EQUITY_SYMBOL_MISSING")
            return f"NSE:{symbol}"

        # Existing option tokens -> production FYERS option resolver.
        if exchange in {"NFO", "BFO"} and instrument_type == "OPTIDX":
            symbol = row_symbol or trading
            market = None
            if symbol.startswith("NIFTY") and not symbol.startswith(("BANKNIFTY", "FINNIFTY")):
                market = "NIFTY"
            elif symbol.startswith("SENSEX") and not symbol.startswith("SENSEX50"):
                market = "SENSEX"
            if market is None:
                raise FyersLegacyIdentityResolutionError("UNSUPPORTED_OPTION_MARKET")

            expiry_text = _text((row or {}).get("expiry"))
            raw_strike = (row or {}).get("strike")
            option_type = "CE" if symbol.endswith("CE") else "PE" if symbol.endswith("PE") else ""
            try:
                expiry = datetime.strptime(expiry_text.upper(), "%d%b%Y").date()
                strike = float(raw_strike) / 100.0
            except (TypeError, ValueError) as exc:
                raise FyersLegacyIdentityResolutionError(
                    "OPTION_METADATA_INVALID"
                ) from exc
            if strike <= 0 or option_type not in {"CE", "PE"}:
                raise FyersLegacyIdentityResolutionError("OPTION_METADATA_INVALID")

            return self._resolved_symbol(
                market_symbol=market,
                instrument_type="OPTION",
                as_of=self._clock(),
                expiry=expiry,
                strike=strike,
                option_type=option_type,
            )

        raise FyersLegacyIdentityResolutionError(
            f"UNMAPPED_LEGACY_IDENTITY:{exchange}:{token}"
        )
