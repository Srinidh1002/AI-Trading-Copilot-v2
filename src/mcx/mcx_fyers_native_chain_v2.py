"""Native FYERS option-chain adapter for MCX PAPER analysis.

Design:
- one FYERS optionchain request for option analytics;
- one FYERS quote request for futures LTP;
- zero per-option depth requests while building the chain;
- market depth remains reserved for executable PAPER entry/exit evidence;
- no orders;
- no Angel fallback;
- no certification mutation.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from mcx.mcx_contracts import PRODUCTS
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)


IST = ZoneInfo("Asia/Kolkata")

SUPPORTED_PRODUCTS = (
    "CRUDEOILM",
    "GOLDM",
    "SILVERM",
)


class MCXFyersNativeChainError(RuntimeError):
    """Native MCX FYERS chain failed closed."""


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _expiry_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise MCXFyersNativeChainError(
            "option expiry is required"
        )

    try:
        expiry = date.fromisoformat(
            value.strip()[:10]
        )
    except ValueError as exc:
        raise MCXFyersNativeChainError(
            "option expiry must be ISO date"
        ) from exc

    dt = datetime.combine(
        expiry,
        time(0, 0),
        tzinfo=IST,
    )

    return int(dt.timestamp())


class MCXFyersNativeChainV2:
    """Rate-safe native FYERS MCX chain builder."""

    provider = "FYERS"
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    live_execution_eligible = False
    per_contract_depth_requests = 0

    def __init__(
        self,
        *,
        data_client,
        identity,
        data_api,
        clock=None,
    ):
        if data_client is None:
            raise ValueError(
                "data_client is required"
            )

        if identity is None:
            raise ValueError(
                "identity is required"
            )

        if data_api is None:
            raise ValueError(
                "data_api is required"
            )

        self._provider = (
            FyersOptionChainProviderV2(
                data_client
            )
        )

        self._identity = identity
        self._data = data_api

        self._clock = (
            clock
            or (lambda: datetime.now(IST))
        )

    def build(
        self,
        product,
        *,
        window_steps=20,
        as_of=None,
    ):
        product = (
            str(product or "")
            .upper()
            .strip()
        )

        if product not in SUPPORTED_PRODUCTS:
            raise MCXFyersNativeChainError(
                f"unsupported product: {product!r}"
            )

        if product not in PRODUCTS:
            raise MCXFyersNativeChainError(
                f"product authority missing: {product}"
            )

        if (
            not isinstance(window_steps, int)
            or window_steps <= 0
        ):
            raise MCXFyersNativeChainError(
                "window_steps must be positive"
            )

        kwargs = {}

        if as_of is not None:
            kwargs["as_of"] = as_of

        identity = (
            self._identity.resolve_active(
                product,
                **kwargs,
            )
        )

        if identity.get("status") != "OK":
            return {
                "status": identity.get(
                    "status",
                    "EVIDENCE_UNAVAILABLE_IDENTITY",
                ),
                "provider": "FYERS",
                "product": product,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        future = identity.get("futures") or {}

        future_symbol = str(
            future.get("symbol") or ""
        ).strip()

        future_token = str(
            future.get("token") or ""
        ).strip()

        if not future_symbol or not future_token:
            return {
                "status": "FUTURE_IDENTITY_UNAVAILABLE",
                "provider": "FYERS",
                "product": product,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        try:
            quote = self._data.ltpData(
                "MCX",
                future_symbol,
                future_token,
            )
        except Exception as exc:
            return {
                "status": "FUTURE_QUOTE_UNAVAILABLE",
                "reason": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "provider": "FYERS",
                "product": product,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        quote_data = (
            quote.get("data", {})
            if isinstance(quote, dict)
            else {}
        )

        future_ltp = _number(
            quote_data.get("ltp")
        )

        if future_ltp <= 0:
            return {
                "status": "FUTURE_LTP_ZERO",
                "provider": "FYERS",
                "product": product,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        step = float(
            PRODUCTS[product][
                "strike_interval"
            ]
        )

        atm = round(
            future_ltp / step
        ) * step

        expiry = identity.get(
            "option_expiry"
        )

        expiry_ts = _expiry_timestamp(
            expiry
        )

        # F8's canonical MCX underlying shape.
        underlying_symbol = (
            f"MCX:{product}"
        )

        try:
            native = (
                self._provider
                .get_option_chain(
                    underlying_symbol=(
                        underlying_symbol
                    ),
                    strike_count=(
                        window_steps
                    ),
                    expiry_timestamp=(
                        expiry_ts
                    ),
                )
            )
        except Exception as exc:
            return {
                "status": "OPTION_CHAIN_UNAVAILABLE",
                "reason": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "provider": "FYERS",
                "product": product,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        if (
            native.get("request_count") != 1
            or native.get(
                "per_contract_depth_requests"
            ) != 0
        ):
            return {
                "status": "PROVIDER_REQUEST_CONTRACT_INVALID",
                "provider": "FYERS",
                "product": product,
                "request_count": native.get(
                    "request_count"
                ),
                "per_contract_depth_requests": (
                    native.get(
                        "per_contract_depth_requests"
                    )
                ),
            }

        calls = identity.get(
            "calls",
            {},
        )

        puts = identity.get(
            "puts",
            {},
        )

        if not calls or not puts:
            return {
                "status": "OPTION_IDENTITY_UNAVAILABLE",
                "provider": "FYERS",
                "product": product,
                "request_count": 1,
                "per_contract_depth_requests": 0,
            }

        low = atm - (
            window_steps * step
        )

        high = atm + (
            window_steps * step
        )

        ce_data = {}
        pe_data = {}

        identity_mismatch_count = 0

        rows = native.get(
            "rows",
            (),
        )

        for row in rows:
            if not isinstance(row, dict):
                continue

            strike = _number(
                row.get("strike"),
                default=-1,
            )

            if strike < low or strike > high:
                continue

            option_type = str(
                row.get("type") or ""
            ).upper()

            if option_type == "CE":
                expected = calls.get(
                    strike
                )
                target = ce_data
            elif option_type == "PE":
                expected = puts.get(
                    strike
                )
                target = pe_data
            else:
                continue

            if not expected:
                identity_mismatch_count += 1
                continue

            expected_symbol = str(
                expected.get(
                    "provider_symbol"
                )
                or expected.get("symbol")
                or ""
            ).strip()

            provider_symbol = str(
                row.get("symbol") or ""
            ).strip()

            if (
                not expected_symbol
                or provider_symbol
                != expected_symbol
            ):
                identity_mismatch_count += 1
                continue

            target[strike] = {
                "symbol": expected[
                    "symbol"
                ],
                "token": expected[
                    "token"
                ],
                "provider_symbol": (
                    provider_symbol
                ),
                "provider_token": (
                    row.get("token")
                ),
                "ltp": _number(
                    row.get("ltp")
                ),
                "oi": _integer(
                    row.get("oi")
                ),
                "vol": _integer(
                    row.get("volume")
                ),
                "bid": _number(
                    row.get("bid")
                ),
                "ask": _number(
                    row.get("ask")
                ),
            }

        if not ce_data or not pe_data:
            return {
                "status": "NATIVE_CHAIN_IDENTITY_MISMATCH",
                "provider": "FYERS",
                "product": product,
                "request_count": 1,
                "per_contract_depth_requests": 0,
                "identity_mismatch_count": (
                    identity_mismatch_count
                ),
            }

        total_ce_oi = sum(
            item["oi"]
            for item
            in ce_data.values()
        )

        total_pe_oi = sum(
            item["oi"]
            for item
            in pe_data.values()
        )

        pcr_oi = (
            round(
                total_pe_oi
                / total_ce_oi,
                4,
            )
            if total_ce_oi > 0
            else None
        )

        all_strikes = sorted(
            set(ce_data)
            | set(pe_data)
        )

        max_pain = None

        if all_strikes:
            pain = []

            for test in all_strikes:
                total = 0.0

                for strike, item in (
                    ce_data.items()
                ):
                    if test > strike:
                        total += (
                            (test - strike)
                            * item["oi"]
                        )

                for strike, item in (
                    pe_data.items()
                ):
                    if test < strike:
                        total += (
                            (strike - test)
                            * item["oi"]
                        )

                pain.append(
                    (test, total)
                )

            if pain:
                max_pain = min(
                    pain,
                    key=lambda pair: pair[1],
                )[0]

        top_ce = sorted(
            ce_data.items(),
            key=lambda pair: (
                pair[1]["oi"]
            ),
            reverse=True,
        )[:3]

        top_pe = sorted(
            pe_data.items(),
            key=lambda pair: (
                pair[1]["oi"]
            ),
            reverse=True,
        )[:3]

        return {
            "status": "OK",
            "provider": "FYERS",
            "product": product,
            "expiry": expiry,
            "future": future_symbol,
            "future_token": (
                future_token
            ),
            "future_ltp": future_ltp,
            "atm": atm,
            "ce_data": ce_data,
            "pe_data": pe_data,
            "pcr_oi": pcr_oi,
            "max_pain": max_pain,
            "resistance": [
                strike
                for strike, _
                in top_ce
            ],
            "support": [
                strike
                for strike, _
                in top_pe
            ],
            "option_chain_request_count": 1,
            "future_quote_request_count": 1,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "identity_mismatch_count": (
                identity_mismatch_count
            ),
            "fetched_at": (
                self._clock()
                .isoformat()
            ),
        }
