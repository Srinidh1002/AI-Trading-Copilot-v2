from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class FyersResponseNormalizationError(ValueError):
    """Raised when a FYERS market-data response cannot be normalized safely."""


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FyersResponseNormalizationError(
            f"{field} must be a mapping"
        )
    return value


def _require_ok(response: Mapping[str, Any]) -> None:
    if response.get("s") != "ok":
        raise FyersResponseNormalizationError(
            "FYERS response status is not ok"
        )


def _number(
    value: object,
    *,
    field: str,
    allow_zero: bool = True,
) -> float:
    if not isinstance(value, (int, float)):
        raise FyersResponseNormalizationError(
            f"{field} must be numeric"
        )

    result = float(value)

    if allow_zero:
        valid = result >= 0
    else:
        valid = result > 0

    if not valid:
        raise FyersResponseNormalizationError(
            f"{field} has invalid value"
        )

    return result


def _quote_entry(
    response: Mapping[str, Any],
    provider_symbol: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    _require_ok(response)

    rows = response.get("d")

    if not isinstance(rows, Sequence) or isinstance(
        rows,
        (str, bytes),
    ):
        raise FyersResponseNormalizationError(
            "FYERS quote response d must be a sequence"
        )

    candidates: list[Mapping[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, Mapping):
            continue

        if raw.get("n") == provider_symbol:
            candidates.append(raw)
            continue

        value = raw.get("v")

        if (
            isinstance(value, Mapping)
            and value.get("symbol") == provider_symbol
        ):
            candidates.append(raw)

    if len(candidates) != 1:
        raise FyersResponseNormalizationError(
            "expected exactly one FYERS quote row"
        )

    envelope = candidates[0]

    payload = envelope.get("v", envelope)

    return envelope, _mapping(
        payload,
        field="quote payload",
    )


def normalize_ltp_data(
    response: Mapping[str, Any],
    *,
    provider_symbol: str,
    exchange: str,
    tradingsymbol: str,
    symboltoken: str,
) -> dict[str, object]:
    """Convert FYERS quotes() output to the active Angel ltpData shape."""

    envelope, payload = _quote_entry(
        response,
        provider_symbol,
    )

    ltp = _number(
        payload.get("lp"),
        field="lp",
        allow_zero=False,
    )

    data: dict[str, object] = {
        "exchange": str(exchange),
        "tradingsymbol": str(tradingsymbol),
        "symboltoken": str(symboltoken),
        "ltp": ltp,
    }

    timestamp = payload.get("tt")

    if isinstance(timestamp, (int, float)):
        data["exchange_timestamp"] = timestamp
        data["timestamp"] = timestamp

    fy_token = payload.get("fyToken")

    if fy_token is not None:
        data["fyToken"] = str(fy_token)

    bid = payload.get("bid")

    if isinstance(bid, (int, float)):
        data["bid"] = float(bid)

    ask = payload.get("ask")

    if isinstance(ask, (int, float)):
        data["ask"] = float(ask)

    volume = payload.get(
        "volume",
        payload.get("v"),
    )

    if isinstance(volume, (int, float)):
        data["volume"] = float(volume)

    # Weighted-constituent analysis compares LTP with the previous trading
    # session close. FYERS quote payloads expose that evidence as
    # prev_close_price. Preserve the provider value directly when present.
    previous_close = None
    previous_close_source = None
    for field in (
        "prev_close_price",
        "prev_close",
        "close_price",
        "c",
    ):
        value = payload.get(field)
        if isinstance(value, (int, float)) and float(value) > 0:
            previous_close = float(value)
            previous_close_source = field
            break

    # Quotes also expose absolute change (`ch`). FYERS defines that value as
    # LTP - previous close, so it is a deterministic fallback when the direct
    # previous-close field is omitted. Never invent a close without either
    # provider-supplied previous-close or provider-supplied change evidence.
    if previous_close is None:
        change = payload.get("ch")
        if isinstance(change, (int, float)):
            derived = ltp - float(change)
            if derived > 0:
                previous_close = derived
                previous_close_source = "DERIVED_FROM_PROVIDER_CHANGE"

    if previous_close is not None:
        data["close"] = previous_close
        data["previous_close"] = previous_close
        data["previous_close_source"] = previous_close_source

    return {
        "status": True,
        "data": data,
    }


def normalize_history(
    response: Mapping[str, Any],
) -> dict[str, object]:
    """Convert FYERS history() output to the active getCandleData shape."""

    _require_ok(response)

    candles = response.get("candles")

    if not isinstance(candles, list):
        raise FyersResponseNormalizationError(
            "FYERS history candles must be a list"
        )

    normalized: list[list[object]] = []

    for index, candle in enumerate(candles):
        if not isinstance(candle, list) or len(candle) < 6:
            raise FyersResponseNormalizationError(
                f"invalid candle at index {index}"
            )

        normalized.append(
            list(candle)
        )

    return {
        "status": True,
        "data": normalized,
    }


def _depth_payload(
    response: Mapping[str, Any],
    provider_symbol: str,
) -> Mapping[str, Any]:
    _require_ok(response)

    root = _mapping(
        response.get("d"),
        field="depth d",
    )

    if provider_symbol in root:
        return _mapping(
            root[provider_symbol],
            field="depth symbol payload",
        )

    if root.get("symbol") == provider_symbol:
        return root

    raise FyersResponseNormalizationError(
        "FYERS depth symbol payload not found"
    )


def _levels(
    value: object,
) -> list[dict[str, object]]:
    if value is None:
        return []

    if isinstance(value, Mapping):
        raw_levels: Sequence[object] = [value]

    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes),
    ):
        raw_levels = value

    else:
        return []

    result: list[dict[str, object]] = []

    for raw in raw_levels:
        if not isinstance(raw, Mapping):
            continue

        price = raw.get("price")

        if not isinstance(price, (int, float)):
            continue

        item: dict[str, object] = {
            "price": float(price),
        }

        for source, target in (
            ("volume", "quantity"),
            ("qty", "quantity"),
            ("ord", "orders"),
        ):
            value = raw.get(source)

            if isinstance(value, (int, float)):
                item[target] = value

        result.append(item)

    return result


def normalize_full_market_data(
    response: Mapping[str, Any],
    *,
    provider_symbol: str,
    symboltoken: str,
) -> dict[str, object]:
    """Convert FYERS depth() output into getMarketData('FULL') compatibility."""

    payload = _depth_payload(
        response,
        provider_symbol,
    )

    ltp = _number(
        payload.get("ltp"),
        field="ltp",
        allow_zero=False,
    )

    buy = _levels(
        payload.get(
            "bids",
            payload.get("bid"),
        )
    )

    sell = _levels(
        payload.get(
            "ask",
            payload.get("asks"),
        )
    )

    fetched: dict[str, object] = {
        "symbolToken": str(symboltoken),
        "ltp": ltp,
        "depth": {
            "buy": buy,
            "sell": sell,
        },
        "bestFiveBuyData": buy,
        "bestFiveSellData": sell,
    }

    if buy:
        fetched["bid"] = buy[0]["price"]

    if sell:
        fetched["ask"] = sell[0]["price"]

    # FYERS depth `ltt` is the provider-side live market-depth update time.
    # Preserve it directly for execution freshness. Do not substitute quote
    # `tt`: live MCX evidence proved that quotes `tt` is only a trading-date
    # anchor and is not suitable as execution freshness evidence.
    depth_timestamp = payload.get("ltt")

    if isinstance(depth_timestamp, (int, float)):
        fetched["exchange_timestamp"] = depth_timestamp
        fetched["timestamp"] = depth_timestamp

    mappings = (
        ("oi", "opnInterest"),
        ("volume", "tradeVolume"),
        ("v", "tradeVolume"),
        ("o", "open"),
        ("h", "high"),
        ("l", "low"),
        ("c", "close"),
    )

    for source, target in mappings:
        value = payload.get(source)

        if isinstance(value, (int, float)):
            fetched[target] = value

    return {
        "status": True,
        "data": {
            "fetched": [
                fetched
            ],
        },
    }


def normalize_option_chain(
    response: Mapping[str, Any],
) -> tuple[dict[str, object], ...]:
    """Normalize FYERS optionchain() rows without inventing missing fields."""

    _require_ok(response)

    data = _mapping(
        response.get("data"),
        field="optionchain data",
    )

    rows = data.get("optionsChain")

    if not isinstance(rows, list):
        raise FyersResponseNormalizationError(
            "optionsChain must be a list"
        )

    result: list[dict[str, object]] = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue

        option_type = str(
            row.get("option_type")
            or ""
        ).upper()

        if option_type not in {
            "CE",
            "PE",
        }:
            continue

        symbol = row.get("symbol")
        strike = row.get("strike_price")
        ltp = row.get("ltp")

        if not isinstance(symbol, str) or not symbol:
            raise FyersResponseNormalizationError(
                "option symbol missing"
            )

        if not isinstance(strike, (int, float)):
            raise FyersResponseNormalizationError(
                "option strike missing"
            )

        if not isinstance(ltp, (int, float)):
            raise FyersResponseNormalizationError(
                "option ltp missing"
            )

        normalized: dict[str, object] = {
            "symbol": symbol,
            "strike": float(strike),
            "type": option_type,
            "ltp": float(ltp),
        }

        optional_fields = (
            ("oi", "oi"),
            ("oich", "oich"),
            ("prev_oi", "prev_oi"),
            ("volume", "volume"),
            ("bid", "bid"),
            ("ask", "ask"),
            ("fyToken", "token"),
            ("expiry", "expiry"),
        )

        for source, target in optional_fields:
            value = row.get(source)

            if value is not None:
                normalized[target] = value

        result.append(normalized)

    if not result:
        raise FyersResponseNormalizationError(
            "no CE/PE option rows found"
        )

    return tuple(result)
