from __future__ import annotations

import time

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")
MCX_IST_CLOSE = dtime(hour=23, minute=30, second=0)
NSE_BSE_IST_CLOSE = dtime(hour=15, minute=30, second=0)


def _infer_market_close_hhmm(underlying_symbol: str):
    """Return the market close time appropriate for the underlying.

    Rule:
      * "MCX:" prefix  -> MCX commodity close 23:30 IST
      * "NSE:" or "BSE:" prefix -> equity derivatives close 15:30 IST
      * no recognisable prefix  -> 15:30 IST (safe index default)
    """
    sym = str(underlying_symbol or "").strip().upper()
    if sym.startswith("MCX:"):
        return MCX_IST_CLOSE
    return NSE_BSE_IST_CLOSE



from collections.abc import Mapping

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
    normalize_option_chain,
)


def _expiry_timestamp_for(expiry_date: str, market_close=None):
    """
    Return the FYERS-compatible epoch (int) for an MCX option expiry.

    Convention verified against live data: the timestamp is MCX close
    (23:30 IST) on the expiry date. Returns None for invalid input.
    """
    text = str(expiry_date or "").strip()
    if not text:
        return None
    if market_close is None:
        market_close = MCX_IST_CLOSE
    try:
        dt = datetime.strptime(text, "%Y-%m-%d").replace(
            hour=market_close.hour,
            minute=market_close.minute,
            second=market_close.second,
            tzinfo=IST,
        )
    except ValueError:
        return None
    return int(dt.timestamp())


_MONTH_ABBR = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}


def _canonical_expiry_date(value) -> str:
    text = str(value or "").strip()

    if not text:
        return ""

    prefix = text[:10]

    if len(prefix) == 10 and prefix[4] == "-" and prefix[7] == "-":
        return prefix

    parts = prefix.split("-")

    if (
        len(parts) == 3
        and len(parts[0]) == 2
        and len(parts[1]) == 2
        and len(parts[2]) == 4
    ):
        return parts[2] + "-" + parts[1] + "-" + parts[0]

    # Phase 9.3 - DDMMMYYYY (e.g. 06OCT2026, 25SEP2026)
    if len(prefix) >= 9:
        _d = prefix[:2]
        _m = prefix[2:5].upper()
        _y = prefix[5:9]
        if _d.isdigit() and _m in _MONTH_ABBR and _y.isdigit():
            return _y + "-" + _MONTH_ABBR[_m] + "-" + _d

    return text


class FyersOptionChainProviderV2:
    """
    Native FYERS option-chain reader.

    This deliberately avoids rebuilding an option chain through many
    per-contract depth requests.
    """

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        client,
    ) -> None:
        self._client = client
        self._expiry_data_cache: dict[str, tuple[float, tuple]] = {}
        self._expiry_cache_ttl = 300.0  # 5 minutes

    def _fetch_expiry_data(self, symbol: str, strike_count: int) -> tuple:
        """Probe FYERS for the expiryData list. Cached per symbol."""
        cached = self._expiry_data_cache.get(symbol)
        now = time.monotonic()
        if cached is not None:
            cached_at, entries = cached
            if now - cached_at < self._expiry_cache_ttl:
                return entries
        try:
            resp = self._client.optionchain(
                data={"symbol": symbol, "strikecount": strike_count}
            )
        except Exception:
            return cached[1] if cached is not None else ()
        if not isinstance(resp, Mapping):
            return cached[1] if cached is not None else ()
        data = resp.get("data")
        if not isinstance(data, Mapping):
            return cached[1] if cached is not None else ()
        raw = data.get("expiryData")
        if not isinstance(raw, (list, tuple)):
            return cached[1] if cached is not None else ()
        entries = tuple(dict(x) for x in raw if isinstance(x, Mapping))
        self._expiry_data_cache[symbol] = (now, entries)
        return entries

    def _resolve_expiry_timestamp(
        self,
        *,
        underlying_symbol: str,
        strike_count: int,
        expected_expiry: str,
    ):
        """Return FYERS's own timestamp for the requested expiry, or None."""
        target = _canonical_expiry_date(expected_expiry)
        if not target:
            return None
        for item in self._fetch_expiry_data(underlying_symbol.strip(), strike_count):
            if _canonical_expiry_date(item.get("date")) != target:
                continue
            raw_ts = item.get("expiry")
            if raw_ts is None:
                return None
            try:
                return int(raw_ts)
            except (TypeError, ValueError):
                return None
        return None

    def get_option_chain(
        self,
        *,
        underlying_symbol: str,
        strike_count: int,
        expiry_timestamp: int | str | None = None,
        expected_expiry: str | None = None,
    ):
        if (
            not isinstance(
                underlying_symbol,
                str,
            )
            or not underlying_symbol.strip()
        ):
            raise ValueError("underlying_symbol is required")

        if (
            not isinstance(
                strike_count,
                int,
            )
            or strike_count <= 0
        ):
            raise ValueError("strike_count must be positive")

        request: dict[
            str,
            object,
        ] = {
            "symbol": underlying_symbol.strip(),
            "strikecount": strike_count,
        }

        if expiry_timestamp is not None and str(expiry_timestamp).strip():
            request["timestamp"] = expiry_timestamp
        elif expected_expiry is not None:
            # Phase 9.7 - FYERS is the source of truth for its own
            # expiry timestamps. Probe (cached 5 min) to get expiryData,
            # find the entry matching our target date, and use FYERS's
            # own epoch. Avoids fragile per-market offset constants.
            _resolved_ts = self._resolve_expiry_timestamp(
                underlying_symbol=underlying_symbol,
                strike_count=strike_count,
                expected_expiry=expected_expiry,
            )
            if _resolved_ts is not None:
                request["timestamp"] = _resolved_ts

        response = self._client.optionchain(data=request)

        if not isinstance(
            response,
            Mapping,
        ):
            raise FyersResponseNormalizationError("invalid FYERS optionchain response")

        data = response.get("data")

        expiry_data = ()

        if isinstance(
            data,
            Mapping,
        ):
            raw_expiry_data = data.get("expiryData")

            if isinstance(
                raw_expiry_data,
                (list, tuple),
            ):
                expiry_data = tuple(
                    dict(item)
                    for item in raw_expiry_data
                    if isinstance(
                        item,
                        Mapping,
                    )
                )

        provider_expiry_date = None
        provider_expiry_timestamp = None

        if expected_expiry is not None:
            target_expiry = _canonical_expiry_date(expected_expiry)

            if not target_expiry:
                raise ValueError("expected_expiry is invalid")

            for item in expiry_data:
                item_date = _canonical_expiry_date(item.get("date"))

                if item_date != target_expiry:
                    continue

                provider_expiry_date = item_date

                provider_expiry_timestamp = item.get("expiry")

                break

            if provider_expiry_timestamp in (
                None,
                "",
            ):
                raise FyersResponseNormalizationError(
                    "FYERS expiryData omitted expected option expiry"
                )

        rows = normalize_option_chain(response)

        return {
            "provider": "FYERS",
            "underlying_symbol": underlying_symbol.strip(),
            "rows": rows,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "data_only": True,
            "live_execution_eligible": False,
            "expiry_data": expiry_data,
            "provider_expiry_date": provider_expiry_date,
            "provider_expiry_timestamp": provider_expiry_timestamp,
        }
