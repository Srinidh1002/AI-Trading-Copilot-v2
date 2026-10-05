"""FYERS-native option-chain adapter for the certified two-index selector.

The existing certified parent/analysis stack expects the same normalized
contract mapping produced by LiveOptionChainBuilder. This adapter provides that
shape from one FYERS optionchain request plus the already-proven production
resolver. It is data-only and has no order or fallback capability.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from math import isfinite
from typing import Callable


class FyersCertifiedOptionChainError(RuntimeError):
    """Certified FYERS option evidence failed closed."""


_MARKET = {
    "NIFTY": ("NIFTY", "NFO"),
    "SENSEX": ("SENSEX", "BFO"),
}


def _date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text.isdigit() and len(text) >= 9:
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc).date()
        except (OSError, OverflowError, ValueError):
            return None
    for fmt in ("%Y-%m-%d", "%d%b%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10] if fmt != "%d%b%Y" else text[:9], fmt).date()
        except ValueError:
            continue
    return None


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise FyersCertifiedOptionChainError(name)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FyersCertifiedOptionChainError(name) from exc
    if not isfinite(result) or result <= 0:
        raise FyersCertifiedOptionChainError(name)
    return result


def _nonnegative(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not isfinite(result) or result < 0:
        return default
    return result


class FyersCertifiedOptionChainBuilderV2:
    """Build the certified option-chain mapping from native FYERS evidence."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        market: str,
        provider,
        resolver,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized = str(market or "").strip().upper()
        if normalized not in _MARKET:
            raise ValueError("market must be NIFTY or SENSEX")
        if provider is None or not callable(getattr(provider, "get_option_chain", None)):
            raise ValueError("FYERS option-chain provider is required")
        if resolver is None or not callable(getattr(resolver, "resolve", None)):
            raise ValueError("FYERS production resolver is required")
        self.market = normalized
        self._provider = provider
        self._resolver = resolver
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self._clock):
            raise TypeError("clock")

    def _select_expiry(self, result: Mapping[str, object], rows: Sequence[Mapping[str, object]], now: datetime) -> date:
        candidates = set()
        for row in rows:
            parsed = _date_value(row.get("expiry"))
            if parsed is not None and parsed >= now.date():
                candidates.add(parsed)
        expiry_data = result.get("expiry_data")
        if isinstance(expiry_data, Sequence) and not isinstance(expiry_data, (str, bytes)):
            for item in expiry_data:
                if not isinstance(item, Mapping):
                    continue
                parsed = _date_value(item.get("date"))
                if parsed is not None and parsed >= now.date():
                    candidates.add(parsed)
        if not candidates:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_EXPIRY_UNAVAILABLE")
        return min(candidates)

    @staticmethod
    def _nearby_strikes(rows: Sequence[Mapping[str, object]], spot: float, strikes_each_side: int) -> set[float]:
        strikes = sorted(
            {
                float(row["strike"])
                for row in rows
                if isinstance(row.get("strike"), (int, float))
                and float(row["strike"]) > 0
            }
        )
        if not strikes:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_STRIKES_UNAVAILABLE")
        nearest = min(range(len(strikes)), key=lambda index: abs(strikes[index] - spot))
        start = max(0, nearest - strikes_each_side)
        end = min(len(strikes), nearest + strikes_each_side + 1)
        return set(strikes[start:end])

    def build_chain(
        self,
        underlying,
        spot_price,
        strikes_each_side=5,
        option_exchange="NFO",
    ) -> dict[str, object]:
        expected_underlying, expected_exchange = _MARKET[self.market]
        if str(underlying or "").strip().upper() != expected_underlying:
            raise FyersCertifiedOptionChainError("UNDERLYING_IDENTITY_MISMATCH")
        if str(option_exchange or "").strip().upper() != expected_exchange:
            raise FyersCertifiedOptionChainError("OPTION_EXCHANGE_IDENTITY_MISMATCH")
        if not isinstance(strikes_each_side, int) or strikes_each_side < 0:
            raise ValueError("strikes_each_side")
        spot = _positive(spot_price, "spot_price")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise FyersCertifiedOptionChainError("CLOCK_NOT_TIMEZONE_AWARE")

        underlying_identity = self._resolver.resolve(
            market_symbol=self.market,
            instrument_type="UNDERLYING",
            as_of=now,
        )
        if not isinstance(underlying_identity, Mapping):
            raise FyersCertifiedOptionChainError("UNDERLYING_RESOLUTION_INVALID")
        provider_underlying = str(
            underlying_identity.get("provider_symbol") or ""
        ).strip()
        if not provider_underlying:
            raise FyersCertifiedOptionChainError("UNDERLYING_PROVIDER_SYMBOL_MISSING")

        result = self._provider.get_option_chain(
            underlying_symbol=provider_underlying,
            strike_count=max(5, strikes_each_side * 2 + 3),
        )
        if not isinstance(result, Mapping):
            raise FyersCertifiedOptionChainError("FYERS_OPTION_CHAIN_INVALID")
        if result.get("provider") != "FYERS":
            raise FyersCertifiedOptionChainError("FYERS_PROVIDER_PROVENANCE_MISSING")
        if result.get("request_count") != 1:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_CHAIN_REQUEST_COUNT_INVALID")
        if result.get("per_contract_depth_requests") != 0:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_DEPTH_FANOUT_PROHIBITED")
        raw_rows = result.get("rows")
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
            raise FyersCertifiedOptionChainError("FYERS_OPTION_ROWS_INVALID")
        rows = tuple(row for row in raw_rows if isinstance(row, Mapping))
        if not rows:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_ROWS_EMPTY")

        expiry = self._select_expiry(result, rows, now)
        selected_rows = []
        for row in rows:
            row_expiry = _date_value(row.get("expiry"))
            if row_expiry is not None and row_expiry != expiry:
                continue
            selected_rows.append(row)
        if not selected_rows:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_EXPIRY_ROWS_EMPTY")

        selected_strikes = self._nearby_strikes(
            selected_rows,
            spot,
            strikes_each_side,
        )

        contracts = []
        seen = set()
        for row in selected_rows:
            option_type = str(row.get("type") or "").strip().upper()
            if option_type not in {"CE", "PE"}:
                continue
            try:
                strike = float(row.get("strike"))
            except (TypeError, ValueError):
                continue
            if strike not in selected_strikes:
                continue

            resolved = self._resolver.resolve(
                market_symbol=self.market,
                instrument_type="OPTION",
                as_of=now,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
            )
            if not isinstance(resolved, Mapping):
                raise FyersCertifiedOptionChainError("OPTION_RESOLUTION_INVALID")
            provider_symbol = str(resolved.get("provider_symbol") or "").strip()
            native_symbol = str(row.get("symbol") or "").strip()
            if not provider_symbol or provider_symbol != native_symbol:
                raise FyersCertifiedOptionChainError(
                    "FYERS_OPTION_IDENTITY_MISMATCH"
                )
            lot_size = resolved.get("lot_size")
            tick_size = resolved.get("tick_size")
            if not isinstance(lot_size, int) or isinstance(lot_size, bool) or lot_size <= 0:
                raise FyersCertifiedOptionChainError("OPTION_LOT_SIZE_UNVERIFIED")
            tick = _positive(tick_size, "OPTION_TICK_SIZE_UNVERIFIED")
            token = str(
                resolved.get("provider_token")
                or row.get("token")
                or provider_symbol
            ).strip()
            identity = (expiry, strike, option_type)
            if not token or identity in seen:
                raise FyersCertifiedOptionChainError("DUPLICATE_OPTION_IDENTITY")
            seen.add(identity)

            bid = _nonnegative(row.get("bid"))
            ask = _nonnegative(row.get("ask"))
            if bid > 0 and ask > 0 and ask < bid:
                raise FyersCertifiedOptionChainError("CROSSED_OPTION_MARKET")

            contracts.append(
                {
                    "provider": "FYERS",
                    "underlying": expected_underlying,
                    "exchange": expected_exchange,
                    "symbol": provider_symbol,
                    "token": token,
                    "provider_symbol": provider_symbol,
                    "provider_token": resolved.get("provider_token") or row.get("token"),
                    "option_type": option_type,
                    "expiry": expiry.isoformat(),
                    "strike": strike,
                    "lot_size": lot_size,
                    "tick_size": tick,
                    "premium": _nonnegative(row.get("ltp")),
                    "ltp": _nonnegative(row.get("ltp")),
                    "bid": bid,
                    "ask": ask,
                    "volume": int(_nonnegative(row.get("volume"))),
                    "open_interest": int(_nonnegative(row.get("oi"))),
                    "change_in_open_interest": int(_nonnegative(row.get("oich"))),
                    "prev_oi": int(_nonnegative(row.get("prev_oi"))),
                }
            )

        if not contracts:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_CONTRACTS_EMPTY")
        option_types = {item["option_type"] for item in contracts}
        if option_types != {"CE", "PE"}:
            raise FyersCertifiedOptionChainError("FYERS_OPTION_TWO_SIDED_CHAIN_REQUIRED")

        contract_tuple = tuple(
            sorted(
                contracts,
                key=lambda item: (float(item["strike"]), str(item["option_type"])),
            )
        )
        return {
            "provider": "FYERS",
            "underlying": expected_underlying,
            "expiry": expiry.isoformat(),
            "spot_price": spot,
            "contracts": contract_tuple,
            "chain_evidence_contracts": contract_tuple,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "data_only": True,
            "live_execution_eligible": False,
            "greek_capture": {
                "state": "UNSUPPORTED_BY_PROVIDER",
                "reason": "OPTION_GREEKS_NOT_INCLUDED_IN_FYERS_NATIVE_CHAIN",
            },
        }
