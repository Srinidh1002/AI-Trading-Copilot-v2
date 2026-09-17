"""Native FYERS option-chain engine with the legacy bot result contract.

One native FYERS optionchain request is cached and projected into the existing
OptionChainEngine shape. Provider symbols are matched back to the exact legacy
contract identities so the selected contract can continue through the narrow
compatibility boundary for a single executable depth quote.
"""
from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)


class FyersNativeOptionChainError(RuntimeError):
    """Native chain evidence cannot be used safely."""


class FyersNativeOptionChainEngineV2:
    """FYERS-native replacement for the legacy batched FULL chain reader."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    per_contract_depth_requests = 0

    def __init__(
        self,
        *,
        market: str,
        provider: FyersOptionChainProviderV2,
        resolver,
        legacy_identity_resolver: Callable[[str, str | None, str], str],
        cache_ttl: float = 60.0,
        native_strike_count: int = 10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        market = str(market).upper().strip()
        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market must be NIFTY or SENSEX")
        if provider is None or not hasattr(provider, "get_option_chain"):
            raise ValueError("native FYERS option-chain provider is required")
        if resolver is None or not hasattr(resolver, "resolve"):
            raise ValueError("production resolver is required")
        if not callable(legacy_identity_resolver):
            raise ValueError("legacy_identity_resolver must be callable")
        if cache_ttl <= 0:
            raise ValueError("cache_ttl must be positive")
        if not isinstance(native_strike_count, int) or native_strike_count <= 0:
            raise ValueError("native_strike_count must be positive")

        self.market = market
        self._provider = provider
        self._resolver = resolver
        self._legacy_identity_resolver = legacy_identity_resolver
        self.cache_ttl = float(cache_ttl)
        self.native_strike_count = native_strike_count
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._raw_cache: dict[str, object] | None = None
        self._raw_cache_at = 0.0

    @property
    def interval(self) -> int:
        return 50 if self.market == "NIFTY" else 100

    def _underlying_symbol(self) -> str:
        resolved = self._resolver.resolve(
            market_symbol=self.market,
            instrument_type="UNDERLYING",
            as_of=self._clock(),
        )
        if not isinstance(resolved, Mapping):
            raise FyersNativeOptionChainError("UNDERLYING_RESOLUTION_INVALID")
        symbol = resolved.get("provider_symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise FyersNativeOptionChainError("UNDERLYING_SYMBOL_MISSING")
        return symbol.strip()

    def _native_rows(self, *, force: bool) -> tuple[Mapping[str, Any], ...]:
        now = time.monotonic()
        if (
            not force
            and self._raw_cache is not None
            and now - self._raw_cache_at < self.cache_ttl
        ):
            return self._raw_cache["rows"]  # type: ignore[return-value]

        result = self._provider.get_option_chain(
            underlying_symbol=self._underlying_symbol(),
            strike_count=self.native_strike_count,
        )
        if not isinstance(result, Mapping):
            raise FyersNativeOptionChainError("NATIVE_CHAIN_INVALID")
        rows = result.get("rows")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise FyersNativeOptionChainError("NATIVE_CHAIN_ROWS_INVALID")
        if result.get("request_count") != 1:
            raise FyersNativeOptionChainError("NATIVE_CHAIN_REQUEST_COUNT_INVALID")
        if result.get("per_contract_depth_requests") != 0:
            raise FyersNativeOptionChainError("DEPTH_FANOUT_PROHIBITED")

        normalized = tuple(row for row in rows if isinstance(row, Mapping))
        if not normalized:
            raise FyersNativeOptionChainError("NATIVE_CHAIN_EMPTY")
        self._raw_cache = {"rows": normalized}
        self._raw_cache_at = now
        return normalized

    @staticmethod
    def _expiry_text(value: object) -> str:
        return str(value or "").strip().upper()

    def _expected_contracts(
        self,
        *,
        expiry: str,
        atm_strike: float,
        instruments: Sequence[Mapping[str, Any]],
        strike_range: float,
    ) -> tuple[dict[str, tuple[float, str, Mapping[str, Any]]], int]:
        expected: dict[str, tuple[float, str, Mapping[str, Any]]] = {}
        identity_failures = 0
        expiry_norm = self._expiry_text(expiry)

        for inst in instruments:
            if not isinstance(inst, Mapping):
                continue
            if str(inst.get("market") or "").upper() != self.market:
                continue
            if self._expiry_text(inst.get("expiry")) != expiry_norm:
                continue
            opt_type = str(inst.get("type") or "").upper()
            if opt_type not in {"CE", "PE"}:
                continue
            try:
                strike = float(inst.get("strike"))
            except (TypeError, ValueError):
                continue
            if abs(strike - float(atm_strike)) > float(strike_range) + 1e-9:
                continue

            exchange = str(inst.get("exchange") or "").strip()
            legacy_symbol = str(inst.get("symbol") or "").strip()
            legacy_token = str(inst.get("token") or "").strip()
            if not exchange or not legacy_symbol or not legacy_token:
                identity_failures += 1
                continue
            try:
                provider_symbol = self._legacy_identity_resolver(
                    exchange,
                    legacy_symbol,
                    legacy_token,
                )
            except Exception:
                identity_failures += 1
                continue
            if not isinstance(provider_symbol, str) or not provider_symbol.strip():
                identity_failures += 1
                continue
            if provider_symbol in expected:
                raise FyersNativeOptionChainError(
                    f"DUPLICATE_PROVIDER_OPTION_IDENTITY:{provider_symbol}"
                )
            expected[provider_symbol.strip()] = (strike, opt_type, inst)

        return expected, identity_failures

    @staticmethod
    def _number(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def fetch(
        self,
        expiry,
        atm_strike,
        instruments,
        strike_range=500,
        force=False,
    ) -> dict[str, object]:
        """Return the existing OptionChainEngine shape from one native chain call."""
        if not isinstance(expiry, str) or not expiry.strip():
            return {"status": "EVIDENCE_UNAVAILABLE", "reason": "EXPIRY_REQUIRED"}
        if not isinstance(instruments, Sequence) or isinstance(instruments, (str, bytes)):
            return {"status": "EVIDENCE_UNAVAILABLE", "reason": "INSTRUMENTS_REQUIRED"}
        try:
            atm = float(atm_strike)
            range_value = float(strike_range)
        except (TypeError, ValueError):
            return {"status": "EVIDENCE_UNAVAILABLE", "reason": "INVALID_STRIKE_RANGE"}
        if atm <= 0 or range_value <= 0:
            return {"status": "EVIDENCE_UNAVAILABLE", "reason": "INVALID_STRIKE_RANGE"}

        expected, identity_failures = self._expected_contracts(
            expiry=expiry,
            atm_strike=atm,
            instruments=instruments,
            strike_range=range_value,
        )
        if not expected:
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "reason": "NO_EXPECTED_CONTRACT_IDENTITIES",
                "identity_resolution_failures": identity_failures,
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        try:
            native_rows = self._native_rows(force=bool(force))
        except Exception as exc:
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "reason": f"NATIVE_CHAIN_ERROR:{type(exc).__name__}",
                "request_count": 0,
                "per_contract_depth_requests": 0,
            }

        ce_data: dict[float, dict[str, object]] = {}
        pe_data: dict[float, dict[str, object]] = {}
        total_ce_oi = total_pe_oi = 0
        total_ce_vol = total_pe_vol = 0
        matched_symbols: set[str] = set()
        relevant_native_rows = 0

        for row in native_rows:
            try:
                strike = float(row.get("strike"))
            except (TypeError, ValueError):
                continue
            if abs(strike - atm) > range_value + 1e-9:
                continue
            opt_type = str(row.get("type") or "").upper()
            if opt_type not in {"CE", "PE"}:
                continue
            relevant_native_rows += 1
            provider_symbol = str(row.get("symbol") or "").strip()
            expected_entry = expected.get(provider_symbol)
            if expected_entry is None:
                continue
            expected_strike, expected_type, inst = expected_entry
            if abs(expected_strike - strike) > 1e-6 or expected_type != opt_type:
                continue

            ltp = self._number(row.get("ltp"))
            bid = self._number(row.get("bid"))
            ask = self._number(row.get("ask"))
            oi = int(self._number(row.get("oi")))
            volume = int(self._number(row.get("volume")))
            spread = (ask - bid) if bid > 0 and ask > 0 and ask >= bid else None
            spread_pct = (
                (spread / ltp) * 100.0
                if spread is not None and ltp > 0
                else None
            )
            item = {
                "strike": expected_strike,
                "type": expected_type,
                "symbol": str(inst.get("symbol") or ""),
                "token": str(inst.get("token") or ""),
                "provider_symbol": provider_symbol,
                "provider_token": row.get("token"),
                "ltp": ltp,
                "open": 0.0,
                "high": 0.0,
                "low": 0.0,
                "close": 0.0,
                "volume": volume,
                "oi": oi,
                "bid": bid,
                "ask": ask,
                "bid_ask_source": (
                    "PROVIDER_OPTION_CHAIN" if bid > 0 and ask > 0 else "UNAVAILABLE"
                ),
                "fetched_at": self._clock().isoformat(),
                "spread": spread,
                "spread_pct": spread_pct,
            }
            matched_symbols.add(provider_symbol)
            if expected_type == "CE":
                ce_data[expected_strike] = item
                total_ce_oi += oi
                total_ce_vol += volume
            else:
                pe_data[expected_strike] = item
                total_pe_oi += oi
                total_pe_vol += volume

        expected_count = len(expected)
        matched_count = len(matched_symbols)
        identity_mismatch_count = max(0, relevant_native_rows - matched_count)
        missing_count = max(0, expected_count - matched_count) + identity_failures

        if not ce_data or not pe_data:
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "reason": "NATIVE_EXPIRY_IDENTITY_MISMATCH",
                "market": self.market,
                "expiry": expiry,
                "atm_strike": atm_strike,
                "expected_count": expected_count,
                "matched_count": matched_count,
                "native_relevant_count": relevant_native_rows,
                "identity_mismatch_count": identity_mismatch_count,
                "identity_resolution_failures": identity_failures,
                "request_count": 1,
                "per_contract_depth_requests": 0,
            }

        pcr_oi = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else None
        pcr_vol = (total_pe_vol / total_ce_vol) if total_ce_vol > 0 else None
        atm_ce = ce_data.get(float(atm), {})
        atm_pe = pe_data.get(float(atm), {})
        atm_pcr = None
        if atm_ce.get("ltp") and atm_pe.get("ltp") and float(atm_ce["ltp"]) > 0:
            atm_pcr = float(atm_pe["ltp"]) / float(atm_ce["ltp"])

        result: dict[str, object] = {
            "status": "OK",
            "provider": "FYERS",
            "market": self.market,
            "expiry": expiry,
            "atm_strike": atm_strike,
            "ce_data": ce_data,
            "pe_data": pe_data,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "total_ce_vol": total_ce_vol,
            "total_pe_vol": total_pe_vol,
            "pcr_oi": round(pcr_oi, 4) if pcr_oi is not None else None,
            "pcr_volume": round(pcr_vol, 4) if pcr_vol is not None else None,
            "atm_pcr": round(atm_pcr, 4) if atm_pcr is not None else None,
            "missing_count": missing_count,
            "ce_count": len(ce_data),
            "pe_count": len(pe_data),
            "expected_count": expected_count,
            "matched_count": matched_count,
            "native_relevant_count": relevant_native_rows,
            "identity_mismatch_count": identity_mismatch_count,
            "identity_resolution_failures": identity_failures,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "fetched_at": self._clock().isoformat(),
        }
        result["bias"] = self._classify_bias(result)
        return result

    @staticmethod
    def _classify_bias(chain: Mapping[str, object]) -> str:
        pcr_oi = chain.get("pcr_oi")
        if not isinstance(pcr_oi, (int, float)):
            return "UNKNOWN"
        if pcr_oi > 1.3:
            return "BULLISH"
        if pcr_oi < 0.7:
            return "BEARISH"
        if pcr_oi > 1.1:
            return "WEAK_BULLISH"
        if pcr_oi < 0.9:
            return "WEAK_BEARISH"
        return "NEUTRAL"

    def describe(self, chain) -> str:
        if not chain or chain.get("status") != "OK":
            reason = chain.get("reason") if isinstance(chain, Mapping) else None
            return f"CHAIN_UNAVAILABLE:{reason or 'UNKNOWN'}"
        return (
            f"PCR_OI={chain.get('pcr_oi')} PCR_VOL={chain.get('pcr_volume')} "
            f"ATM_PCR={chain.get('atm_pcr')} bias={chain.get('bias')} "
            f"({chain.get('ce_count')}CE/{chain.get('pe_count')}PE "
            f"missing={chain.get('missing_count')} native_req=1 depth_fanout=0)"
        )
