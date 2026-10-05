"""FYERS-native option capture for the certified two-index PAPER pipeline.

This adapter projects one synchronous FYERS optionchain response into the
existing LiveOptionCaptureResultV1 contract. It does not fabricate exchange
book timestamps: option snapshot time is the local response-receipt timestamp
and is labelled SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any, Callable

from services.contracts.live_option_capture_result_v1 import (
    LiveOptionCaptureResultV1,
)


class FyersCertifiedOptionCaptureError(RuntimeError):
    """FYERS option evidence cannot be projected safely."""


_OPTION_EXCHANGE = {
    "NIFTY": "NFO",
    "SENSEX": "BFO",
}


def _coerce_expiry(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(
                int(value),
                tz=timezone.utc,
            ).date()
        except (OSError, OverflowError, ValueError):
            return None

    text = str(value or "").strip().upper()
    if not text:
        return None
    if text.isdigit() and len(text) >= 9:
        try:
            return datetime.fromtimestamp(
                int(text),
                tz=timezone.utc,
            ).date()
        except (OSError, OverflowError, ValueError):
            return None

    for fmt in ("%Y-%m-%d", "%d%b%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:11], fmt).date()
        except ValueError:
            continue
    return None


def _number(value: object, *, positive: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if positive and result <= 0:
        return None
    return result


def _target_expiry(
    *,
    result: Mapping[str, Any],
    rows: tuple[Mapping[str, Any], ...],
    as_of: date,
) -> date | None:
    row_dates = {
        value
        for row in rows
        if (value := _coerce_expiry(row.get("expiry"))) is not None
        and value >= as_of
    }
    if len(row_dates) == 1:
        return next(iter(row_dates))
    if len(row_dates) > 1:
        return None

    expiry_data = result.get("expiry_data")
    candidates: set[date] = set()
    if isinstance(expiry_data, (tuple, list)):
        for item in expiry_data:
            if not isinstance(item, Mapping):
                continue
            value = (
                _coerce_expiry(item.get("date"))
                or _coerce_expiry(item.get("expiry"))
            )
            if value is not None and value >= as_of:
                candidates.add(value)

    return min(candidates) if candidates else None


class FyersCertifiedOptionCaptureV2:
    """Data-only FYERS-native option capture for NIFTY/SENSEX."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    provider_name = "FYERS"
    timestamp_basis = "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE"

    def __init__(
        self,
        *,
        market: str,
        provider,
        resolver,
        strike_count: int = 10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        market = str(market or "").strip().upper()
        if market not in _OPTION_EXCHANGE:
            raise ValueError("market must be NIFTY or SENSEX")
        if provider is None or not callable(
            getattr(provider, "get_option_chain", None)
        ):
            raise TypeError("provider")
        if resolver is None or not callable(
            getattr(resolver, "resolve", None)
        ):
            raise TypeError("resolver")
        if not isinstance(strike_count, int) or strike_count <= 0:
            raise ValueError("strike_count")

        self.market = market
        self.option_exchange = _OPTION_EXCHANGE[market]
        self.provider = provider
        self.resolver = resolver
        self.strike_count = strike_count
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self.clock):
            raise TypeError("clock")

    def _underlying_symbol(self, at: datetime) -> str:
        resolved = self.resolver.resolve(
            market_symbol=self.market,
            instrument_type="UNDERLYING",
            as_of=at,
        )
        if not isinstance(resolved, Mapping):
            raise FyersCertifiedOptionCaptureError(
                "UNDERLYING_RESOLUTION_INVALID"
            )
        symbol = resolved.get("provider_symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise FyersCertifiedOptionCaptureError(
                "UNDERLYING_PROVIDER_SYMBOL_MISSING"
            )
        return symbol.strip()

    def analyse(self, *args, **kwargs):
        """Legacy full-decision entry point is intentionally unsupported."""
        raise FyersCertifiedOptionCaptureError(
            "FYERS_CERTIFIED_CAPTURE_ONLY"
        )

    def capture_option_inputs(
        self,
        *,
        underlying,
        spot_price,
        option_exchange="NFO",
        strikes_each_side=5,
        provider_timestamp,
        evaluated_at,
    ) -> LiveOptionCaptureResultV1:
        market = str(underlying or "").strip().upper()
        exchange = str(option_exchange or "").strip().upper()
        if market != self.market or exchange != self.option_exchange:
            raise ValueError("certified FYERS option identity mismatch")
        if (
            not isinstance(provider_timestamp, datetime)
            or provider_timestamp.tzinfo is None
            or provider_timestamp.utcoffset() is None
        ):
            raise ValueError("provider_timestamp")
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at")
        if _number(spot_price, positive=True) is None:
            raise ValueError("spot_price")

        request_at = self.clock()
        if (
            not isinstance(request_at, datetime)
            or request_at.tzinfo is None
            or request_at.utcoffset() is None
        ):
            raise ValueError("clock must return timezone-aware datetime")

        try:
            result = self.provider.get_option_chain(
                underlying_symbol=self._underlying_symbol(request_at),
                strike_count=max(
                    self.strike_count,
                    2 * int(strikes_each_side) + 1,
                ),
            )
        except Exception as exc:
            return LiveOptionCaptureResultV1(
                underlying_symbol=self.market,
                option_exchange=self.option_exchange,
                option_chain={"contracts": ()},
                provider_timestamp=request_at,
                evaluated_at=evaluated_at,
                blockers=(
                    f"FYERS_OPTION_CHAIN_{type(exc).__name__.upper()}",
                ),
                metadata={
                    "provider_name": "FYERS",
                    "timestamp_basis": self.timestamp_basis,
                    "request_count": 0,
                },
            )

        if not isinstance(result, Mapping):
            raise FyersCertifiedOptionCaptureError(
                "OPTION_CHAIN_RESULT_INVALID"
            )

        received_at = result.get("response_received_at")
        if (
            not isinstance(received_at, datetime)
            or received_at.tzinfo is None
            or received_at.utcoffset() is None
        ):
            raise FyersCertifiedOptionCaptureError(
                "OPTION_CHAIN_RECEIPT_TIMESTAMP_MISSING"
            )

        raw_rows = result.get("rows")
        rows = tuple(
            row
            for row in (
                raw_rows
                if isinstance(raw_rows, (tuple, list))
                else ()
            )
            if isinstance(row, Mapping)
        )
        expiry = _target_expiry(
            result=result,
            rows=rows,
            as_of=received_at.date(),
        )
        if expiry is None:
            return LiveOptionCaptureResultV1(
                underlying_symbol=self.market,
                option_exchange=self.option_exchange,
                option_chain={"contracts": ()},
                provider_timestamp=received_at,
                evaluated_at=evaluated_at,
                blockers=("FYERS_OPTION_EXPIRY_UNRESOLVED",),
                metadata={
                    "provider_name": "FYERS",
                    "timestamp_basis": self.timestamp_basis,
                    "response_received_at": received_at,
                    "request_count": result.get("request_count", 1),
                },
            )

        contracts = []
        identity_failures = 0
        metadata_failures = 0

        for row in rows:
            option_type = str(row.get("type") or "").strip().upper()
            strike = _number(row.get("strike"), positive=True)
            provider_symbol = str(row.get("symbol") or "").strip()
            row_expiry = _coerce_expiry(row.get("expiry"))

            if option_type not in {"CE", "PE"} or strike is None:
                continue
            if row_expiry is not None and row_expiry != expiry:
                continue

            try:
                resolved = self.resolver.resolve(
                    market_symbol=self.market,
                    instrument_type="OPTION",
                    as_of=received_at,
                    expiry=expiry,
                    strike=float(strike),
                    option_type=option_type,
                )
            except Exception:
                identity_failures += 1
                continue

            if not isinstance(resolved, Mapping):
                identity_failures += 1
                continue
            resolved_symbol = str(
                resolved.get("provider_symbol") or ""
            ).strip()
            if not resolved_symbol or (
                provider_symbol
                and provider_symbol != resolved_symbol
            ):
                identity_failures += 1
                continue

            lot_size = resolved.get("lot_size")
            tick_size = resolved.get("tick_size")
            try:
                lot_size = int(lot_size)
                tick_size = float(tick_size)
            except (TypeError, ValueError):
                metadata_failures += 1
                continue
            if lot_size <= 0 or tick_size <= 0:
                metadata_failures += 1
                continue

            ltp = _number(row.get("ltp"))
            bid = _number(row.get("bid"))
            ask = _number(row.get("ask"))
            if ltp is None or ltp < 0:
                continue
            if bid is not None and ask is not None and ask < bid:
                continue

            token = str(
                resolved.get("provider_token")
                or row.get("token")
                or resolved_symbol
            ).strip()
            if not token:
                identity_failures += 1
                continue

            contract = {
                "token": token,
                "symbol": resolved_symbol,
                "underlying": self.market,
                "exchange": self.option_exchange,
                "strike": float(strike),
                "option_type": option_type,
                "expiry": expiry.isoformat(),
                "lot_size": lot_size,
                "tick_size": tick_size,
                "premium": float(ltp),
                "bid": bid,
                "ask": ask,
                "volume": (
                    int(row["volume"])
                    if isinstance(row.get("volume"), (int, float))
                    and not isinstance(row.get("volume"), bool)
                    and row.get("volume") >= 0
                    else None
                ),
                "open_interest": (
                    int(row["oi"])
                    if isinstance(row.get("oi"), (int, float))
                    and not isinstance(row.get("oi"), bool)
                    and row.get("oi") >= 0
                    else None
                ),
                "change_in_open_interest": (
                    int(row["oich"])
                    if isinstance(row.get("oich"), (int, float))
                    and not isinstance(row.get("oich"), bool)
                    else None
                ),
                "provider_timestamp": received_at,
                "provider_timestamp_basis": self.timestamp_basis,
                "provider": "FYERS",
            }
            contracts.append(contract)

        ce_count = sum(
            1 for item in contracts if item["option_type"] == "CE"
        )
        pe_count = sum(
            1 for item in contracts if item["option_type"] == "PE"
        )
        blockers = ()
        if not contracts or ce_count == 0 or pe_count == 0:
            blockers = ("FYERS_OPTION_CHAIN_INCOMPLETE",)

        return LiveOptionCaptureResultV1(
            underlying_symbol=self.market,
            option_exchange=self.option_exchange,
            option_chain={
                "underlying": self.market,
                "spot_price": float(spot_price),
                "expiry": expiry.isoformat(),
                "contracts": tuple(contracts),
                "chain_evidence_contracts": tuple(contracts),
                "integrity_validated": not blockers,
                "provider": "FYERS",
            },
            provider_timestamp=received_at,
            evaluated_at=evaluated_at,
            blockers=blockers,
            warnings=(
                "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE",
            ),
            metadata={
                "provider_name": "FYERS",
                "timestamp_basis": self.timestamp_basis,
                "response_received_at": received_at,
                "request_count": result.get("request_count", 1),
                "per_contract_depth_requests": result.get(
                    "per_contract_depth_requests",
                    0,
                ),
                "expiry": expiry.isoformat(),
                "contract_count": len(contracts),
                "ce_count": ce_count,
                "pe_count": pe_count,
                "identity_resolution_failures": identity_failures,
                "metadata_failures": metadata_failures,
            },
        )
