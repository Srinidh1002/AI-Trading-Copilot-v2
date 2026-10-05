"""FYERS-native option capture for the R16 exact-two-index SHADOW path.

The adapter reuses the proven FYERS native option-chain engine, enriches each
matched contract with provider-master metadata, and publishes the existing
LiveOptionCaptureResultV1 shape.  It is read-only and cannot submit orders.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from services.contracts.live_option_capture_result_v1 import (
    LiveOptionCaptureResultV1,
)
from services.core.market_trading_config_v2 import (
    get_market_trading_config,
)

IST = ZoneInfo("Asia/Kolkata")

_MARKET_BY_IDENTITY = {
    ("NIFTY", "NFO"): "NIFTY",
    ("SENSEX", "BFO"): "SENSEX",
}


def load_legacy_index_option_instruments(
    path: str | Path,
) -> dict[str, tuple[dict, ...]]:
    """Load only NIFTY/SENSEX OPTIDX identities needed by the native engine."""

    source = Path(path)
    rows = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("instrument master must be a list")

    output: dict[str, list[dict]] = {
        "NIFTY": [],
        "SENSEX": [],
    }

    for market in output:
        cfg = get_market_trading_config(market)
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol") or "")
            if cfg.symbol_must_contain not in symbol:
                continue
            if any(
                blocked in symbol
                for blocked in cfg.symbol_must_not_contain
            ):
                continue
            if str(row.get("instrumenttype") or "").upper() != "OPTIDX":
                continue

            option_type = (
                "CE"
                if symbol.endswith("CE")
                else "PE"
                if symbol.endswith("PE")
                else None
            )
            if option_type is None:
                continue

            try:
                strike = float(row.get("strike")) / cfg.strike_divisor
            except (TypeError, ValueError):
                continue
            if strike <= 0:
                continue

            expiry = str(row.get("expiry") or "").strip().upper()
            try:
                datetime.strptime(expiry, "%d%b%Y")
            except ValueError:
                continue

            output[market].append(
                {
                    "market": market,
                    "exchange": cfg.derivative_exchange,
                    "expiry": expiry,
                    "strike": strike,
                    "type": option_type,
                    "symbol": symbol,
                    "token": str(row.get("token") or ""),
                }
            )

    return {
        market: tuple(values)
        for market, values in output.items()
    }


class R16FyersNativeOptionCapturePipelineV1:
    """Read-only native FYERS option capture; full analysis is prohibited."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    execution_mode = "PAPER"
    live_execution_eligible = False
    broker_order_submission = False
    mode = "SHADOW_ONLY"

    def __init__(
        self,
        *,
        engines_by_market: Mapping[str, object],
        resolver,
        instruments_by_market: Mapping[str, tuple[dict, ...]],
        clock=None,
    ) -> None:
        self.engines_by_market = dict(engines_by_market)
        self.resolver = resolver
        self.instruments_by_market = {
            str(key).upper(): tuple(value)
            for key, value in instruments_by_market.items()
        }
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self.clock):
            raise TypeError("clock")
        if resolver is None or not callable(getattr(resolver, "resolve", None)):
            raise TypeError("resolver")
        if not callable(getattr(resolver, "nearest_option_expiry", None)):
            raise TypeError("resolver.nearest_option_expiry")

        for market in ("NIFTY", "SENSEX"):
            engine = self.engines_by_market.get(market)
            if engine is None or not callable(getattr(engine, "fetch", None)):
                raise ValueError(f"missing native option engine for {market}")
            if not self.instruments_by_market.get(market):
                raise ValueError(f"missing legacy option identities for {market}")

    @staticmethod
    def _aware(value: object, name: str) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(name)
        return value

    def analyse(self, **_kwargs):
        """Fail closed if the legacy full-decision path is invoked."""
        raise RuntimeError("R16_SHADOW_OPTION_CAPTURE_ONLY")

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
        market = _MARKET_BY_IDENTITY.get(
            (
                str(underlying).strip().upper(),
                str(option_exchange).strip().upper(),
            )
        )
        if market is None:
            raise ValueError("unsupported R16 option identity")

        cfg = get_market_trading_config(market)
        spot = float(spot_price)
        if spot <= 0:
            raise ValueError("spot_price")
        requested_at = self._aware(evaluated_at, "evaluated_at")
        self._aware(provider_timestamp, "provider_timestamp")

        expiry_date = self.resolver.nearest_option_expiry(
            market_symbol=market,
            as_of=requested_at,
            exclude_same_day=cfg.exclude_same_day_expiry,
        )
        expiry_text = expiry_date.strftime("%d%b%Y").upper()
        atm = round(spot / cfg.strike_interval) * cfg.strike_interval
        strike_range = cfg.strike_interval * int(strikes_each_side)

        engine = self.engines_by_market[market]
        chain = engine.fetch(
            expiry_text,
            atm,
            self.instruments_by_market[market],
            strike_range=strike_range,
        )
        received_at = self._aware(self.clock(), "clock")

        if not isinstance(chain, Mapping) or chain.get("status") != "OK":
            reason = (
                str(chain.get("reason") or "UNKNOWN")
                if isinstance(chain, Mapping)
                else "INVALID_NATIVE_CHAIN"
            )
            return LiveOptionCaptureResultV1(
                underlying_symbol=market,
                option_exchange=cfg.derivative_exchange,
                option_chain={
                    "underlying": market,
                    "spot_price": spot,
                    "expiry": expiry_date.isoformat(),
                    "contracts": (),
                    "chain_evidence_contracts": (),
                    "integrity_validated": False,
                },
                provider_timestamp=received_at,
                evaluated_at=received_at,
                blockers=(f"FYERS_NATIVE_OPTION_CHAIN_{reason}",),
                metadata={
                    "provider": "FYERS",
                    "request_count": (
                        chain.get("request_count")
                        if isinstance(chain, Mapping)
                        else None
                    ),
                    "per_contract_depth_requests": (
                        chain.get("per_contract_depth_requests")
                        if isinstance(chain, Mapping)
                        else None
                    ),
                    "timestamp_basis": (
                        "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE_RECEIPT"
                    ),
                    "shadow_only": True,
                },
            )

        contracts = []
        for option_type, key in (("CE", "ce_data"), ("PE", "pe_data")):
            pool = chain.get(key) or {}
            for strike in sorted(pool):
                row = pool[strike]
                if not isinstance(row, Mapping):
                    continue
                resolved = self.resolver.resolve(
                    market_symbol=market,
                    instrument_type="OPTION",
                    as_of=requested_at,
                    expiry=expiry_date,
                    strike=float(strike),
                    option_type=option_type,
                )
                lot_size = resolved.get("lot_size")
                tick_size = resolved.get("tick_size")
                if not isinstance(lot_size, int) or lot_size <= 0:
                    continue
                if not isinstance(tick_size, (int, float)) or float(tick_size) <= 0:
                    continue

                contract = {
                    "exchange": cfg.derivative_exchange,
                    "underlying": market,
                    "token": str(
                        row.get("provider_token")
                        or row.get("token")
                        or resolved.get("provider_token")
                        or ""
                    ),
                    "symbol": str(
                        row.get("provider_symbol")
                        or resolved.get("provider_symbol")
                        or row.get("symbol")
                        or ""
                    ),
                    "strike": float(strike),
                    "option_type": option_type,
                    "expiry": expiry_date.isoformat(),
                    "lot_size": lot_size,
                    "tick_size": float(tick_size),
                    "premium": float(row.get("ltp") or 0.0),
                    "bid": float(row.get("bid") or 0.0),
                    "ask": float(row.get("ask") or 0.0),
                    "volume": int(float(row.get("volume") or 0)),
                    "open_interest": int(float(row.get("oi") or 0)),
                    "change_in_open_interest": (
                        int(float(row.get("change_in_open_interest")))
                        if row.get("change_in_open_interest") is not None
                        else None
                    ),
                    "provider_timestamp": received_at,
                    "provider_timestamp_basis": (
                        "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE_RECEIPT"
                    ),
                    "delta": row.get("delta"),
                    "gamma": row.get("gamma"),
                    "theta": row.get("theta"),
                    "vega": row.get("vega"),
                    "iv": row.get("iv"),
                }
                if (
                    contract["token"]
                    and contract["symbol"]
                    and contract["premium"] > 0
                    and contract["bid"] >= 0
                    and contract["ask"] >= contract["bid"]
                ):
                    contracts.append(contract)

        blockers = []
        if not contracts:
            blockers.append("FYERS_NATIVE_OPTION_CONTRACTS_UNAVAILABLE")

        missing_greeks = sum(
            1
            for row in contracts
            if any(
                row.get(name) is None
                for name in ("delta", "gamma", "theta", "vega", "iv")
            )
        )
        warnings = []
        if missing_greeks:
            warnings.append(
                f"FYERS_OPTION_GREEKS_INCOMPLETE:{missing_greeks}"
            )

        option_chain = {
            "underlying": market,
            "spot_price": spot,
            "expiry": expiry_date.isoformat(),
            "contracts": tuple(contracts),
            "chain_evidence_contracts": tuple(contracts),
            "requested_contracts": int(chain.get("expected_count") or 0),
            "received_contracts": len(contracts),
            "validated_contracts": len(contracts),
            "rejected_contracts": max(
                0,
                int(chain.get("expected_count") or 0) - len(contracts),
            ),
            "integrity_validated": not blockers,
            "full_capture": {
                "requested_contract_count": int(
                    chain.get("expected_count") or 0
                ),
                "fetched_contract_count": len(contracts),
                "unfetched_contract_count": int(
                    chain.get("missing_count") or 0
                ),
                "malformed_contract_count": 0,
                "exchange_identity_verified": True,
            },
            "greek_capture": {
                "state": (
                    "AVAILABLE"
                    if contracts and missing_greeks == 0
                    else "PARTIAL"
                    if contracts
                    else "DATA_UNAVAILABLE"
                ),
                "source": "FYERS_OPTION_CHAIN_API_V3",
            },
        }

        return LiveOptionCaptureResultV1(
            underlying_symbol=market,
            option_exchange=cfg.derivative_exchange,
            option_chain=option_chain,
            provider_timestamp=received_at,
            evaluated_at=received_at,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            metadata={
                "provider": "FYERS",
                "expiry": expiry_date.isoformat(),
                "request_count": chain.get("request_count"),
                "per_contract_depth_requests": chain.get(
                    "per_contract_depth_requests"
                ),
                "timestamp_basis": (
                    "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE_RECEIPT"
                ),
                "option_greeks_source": "FYERS_OPTION_CHAIN_API_V3",
                "shadow_only": True,
            },
        )
