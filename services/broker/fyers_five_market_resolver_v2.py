"""F8 - production FYERS five-market instrument resolver.

Implements the frozen F7 InstrumentResolverV2 protocol for NIFTY, SENSEX,
CRUDEOILM, GOLDM and NATGASMINI. Composes:
  - FYERS public symbol master (offline-testable)
  - native FYERS futures_chain (authoritative for NIFTY/SENSEX futures)

Data-only. No order-capable operations. No certification counter mutations.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone

from services.broker.fyers_symbol_master_v2 import (
    FyersMasterRecordV2,
    FyersSymbolMasterError,
    FyersSymbolMasterIndexV2,
    FyersSymbolMasterStoreV2,
    SUPPORTED_SEGMENTS,
)
from services.contracts.resolved_instrument_v2 import ResolvedInstrumentV2
from services.core.five_market_universe_v2 import get_target_market


class FyersResolutionError(RuntimeError):
    """F8 resolver failed closed."""


_UNDERLYING_BY_MARKET = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

_MARKET_SEGMENTS = {
    "NIFTY": {"underlying": "NSE_CM", "derivative": "NSE_FO"},
    "SENSEX": {"underlying": "BSE_CM", "derivative": "BSE_FO"},
    "CRUDEOILM": {"underlying": "MCX_COM", "derivative": "MCX_COM"},
    "GOLDM": {"underlying": "MCX_COM", "derivative": "MCX_COM"},
    "NATGASMINI": {"underlying": "MCX_COM", "derivative": "MCX_COM"},
}

_VALID_INSTRUMENT_TYPES = ("UNDERLYING", "FUTURE", "OPTION")
_VALID_OPTION_TYPES = ("CE", "PE")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_resolution_id(market_symbol, instrument_type, provider_symbol,
                             expiry, strike, option_type) -> str:
    parts = [
        "FYERS", market_symbol, instrument_type, provider_symbol,
        expiry.isoformat() if expiry else "",
        ("%.4f" % strike) if strike is not None else "",
        option_type or "",
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return "FYR_V2_" + digest[:24]


def _unix_to_date(ts):
    """Unix seconds -> date in IST; None on failure."""
    try:
        n = int(ts)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    try:
        return datetime.fromtimestamp(n, tz=ist).date()
    except (OSError, ValueError, OverflowError):
        return None


def _coerce_date(v) -> date | None:
    """Accept datetime, date, ISO date string, or unix-timestamp
    (string or int). FYERS futures_chain returns unix seconds as
    strings; NSE/BSE master CSVs return ISO date strings.
    """
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return _unix_to_date(int(v))
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if s.isdigit() and len(s) >= 9:
            return _unix_to_date(int(s))
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None

def _extract_rows(response) -> list[Mapping]:
    """Tolerant extraction of a list of row mappings from a FYERS response.

    FYERS responses from the synchronous SDK use both "d" (depth) and
    "data" (futures_chain / optionchain). We accept either, and search
    common nested list keys.
    """
    if not isinstance(response, Mapping):
        return []
    if response.get("s") not in (None, "ok"):
        return []
    for root_key in ("d", "data"):
        root = response.get(root_key)
        if isinstance(root, list):
            return [r for r in root if isinstance(r, Mapping)]
        if isinstance(root, Mapping):
            for key in ("futures", "futures_list", "rows", "data",
                        "contracts", "expiry", "expiries", "list",
                        "optionsChain"):
                val = root.get(key)
                if isinstance(val, list):
                    return [r for r in val if isinstance(r, Mapping)]
    return []

class FyersFiveMarketInstrumentResolverV2:
    """Deterministic FYERS identity resolver for the five-market universe."""

    def __init__(self, *, data_client, master_store=None, clock=None) -> None:
        if data_client is None:
            raise ValueError("data_client is required")
        self._client = data_client
        self._store = master_store or FyersSymbolMasterStoreV2()
        self._clock = clock or _now_utc

    # ---------- public API ----------

    def resolve(self, *, market_symbol, instrument_type, as_of=None,
                expiry=None, strike=None, option_type=None) -> dict:
        market = get_target_market(market_symbol)
        kind = str(instrument_type or "").upper().strip()
        if kind not in _VALID_INSTRUMENT_TYPES:
            raise FyersResolutionError(
                f"unsupported instrument_type: {instrument_type!r}"
            )
        as_of_dt = as_of if as_of is not None else self._clock()
        if not isinstance(as_of_dt, datetime):
            raise FyersResolutionError("as_of must be a datetime")
        if as_of_dt.tzinfo is None or as_of_dt.utcoffset() is None:
            raise FyersResolutionError("as_of must be timezone-aware")

        if kind == "UNDERLYING":
            if expiry is not None or strike is not None or option_type is not None:
                raise FyersResolutionError("UNDERLYING must not carry derivative args")
            return self._resolve_underlying(market, as_of_dt)
        if kind == "FUTURE":
            if strike is not None or option_type is not None:
                raise FyersResolutionError("FUTURE must not carry strike/option_type")
            return self._resolve_future(market, as_of_dt, _coerce_date(expiry) if expiry else None)
        # OPTION
        if strike is None or option_type is None:
            raise FyersResolutionError("OPTION requires strike and option_type")
        if expiry is None:
            raise FyersResolutionError("OPTION requires expiry")
        return self._resolve_option(
            market, as_of_dt, _coerce_date(expiry), float(strike), str(option_type)
        )

    # ---------- UNDERLYING ----------

    def _resolve_underlying(self, market, as_of_dt):
        if market.market_type == "INDEX":
            provider_symbol = _UNDERLYING_BY_MARKET.get(market.symbol)
            if provider_symbol is None:
                raise FyersResolutionError(
                    f"no canonical FYERS underlying for {market.symbol}"
                )
            return self._build(
                market=market,
                instrument_type="UNDERLYING",
                provider_symbol=provider_symbol,
                provider_exchange=market.underlying_exchange,
                provider_token=None,
                expiry=None, strike=None, option_type=None,
                lot_size=None, tick_size=None,
                metadata_status="NOT_APPLICABLE",
                metadata_source=None,
                resolved_at=as_of_dt,
                warnings=(),
            )

        # MCX product root: resolve from master evidence. Prefer an
        # explicit UNDERLYING record if present; otherwise derive the
        # canonical provider symbol from any FUTURE/OPTION row whose
        # underlying_symbol matches the market. Fail closed if no such
        # evidence exists.
        seg = _MARKET_SEGMENTS[market.symbol]["underlying"]
        idx = self._require_index(seg)

        canonical_symbol = f"{market.underlying_exchange}:{market.symbol}"

        explicit = [
            r for r in idx.records
            if r.instrument_kind == "UNDERLYING"
            and r.symbol.upper() == canonical_symbol.upper()
        ]
        if explicit:
            rec = explicit[0]
            return self._build(
                market=market,
                instrument_type="UNDERLYING",
                provider_symbol=rec.symbol,
                provider_exchange=rec.exchange,
                provider_token=rec.provider_token,
                expiry=None, strike=None, option_type=None,
                lot_size=None, tick_size=None,
                metadata_status="NOT_APPLICABLE",
                metadata_source=None,
                resolved_at=as_of_dt,
                warnings=(),
            )

        derived = [
            r for r in idx.records
            if (r.underlying_symbol or "").upper() == market.symbol
        ]
        if not derived:
            raise FyersResolutionError(
                f"MCX underlying for {market.symbol} not present in master"
            )

        return self._build(
            market=market,
            instrument_type="UNDERLYING",
            provider_symbol=canonical_symbol,
            provider_exchange=market.underlying_exchange,
            provider_token=None,
            expiry=None, strike=None, option_type=None,
            lot_size=None, tick_size=None,
            metadata_status="NOT_APPLICABLE",
            metadata_source=None,
            resolved_at=as_of_dt,
            warnings=("underlying_derived_from_master_evidence",),
        )

    # ---------- FUTURE ----------

    def _resolve_future(self, market, as_of_dt, requested_expiry):
        if market.market_type == "INDEX":
            return self._resolve_future_index(market, as_of_dt, requested_expiry)
        return self._resolve_future_mcx(market, as_of_dt, requested_expiry)

    def _resolve_future_index(self, market, as_of_dt, requested_expiry):
        underlying = _UNDERLYING_BY_MARKET[market.symbol]
        try:
            response = self._client.futures_chain({"symbol": underlying})
        except Exception as exc:
            raise FyersResolutionError(
                f"futures_chain failed for {underlying}: {exc}"
            ) from exc
        rows = _extract_rows(response)
        candidates = []
        for row in rows:
            symbol = row.get("symbol") or row.get("fy_symbol")
            expiry = _coerce_date(row.get("expiry") or row.get("expiry_date"))
            if not symbol or not expiry:
                continue
            if expiry <= as_of_dt.date():
                continue
            if requested_expiry is not None and expiry != requested_expiry:
                continue
            candidates.append({
                "symbol": str(symbol),
                "expiry": expiry,
                "token": row.get("fyToken") or row.get("token"),
                "lot": row.get("lot_size") or row.get("lotSize"),
                "tick": row.get("tick_size") or row.get("tickSize"),
            })
        if not candidates:
            raise FyersResolutionError(
                f"no non-expired futures for {market.symbol}"
                + (f" at expiry {requested_expiry}" if requested_expiry else "")
            )
        nearest_expiry = min(c["expiry"] for c in candidates)
        nearest = [c for c in candidates if c["expiry"] == nearest_expiry]
        if len(nearest) > 1:
            distinct = {c["symbol"] for c in nearest}
            if len(distinct) > 1:
                raise FyersResolutionError(
                    f"ambiguous futures for {market.symbol} at {nearest_expiry}"
                )
        chosen = nearest[0]
        meta_status, lot, tick, meta_source, warns = self._classify_metadata(chosen)
        return self._build(
            market=market,
            instrument_type="FUTURE",
            provider_symbol=chosen["symbol"],
            provider_exchange=market.derivative_exchange,
            provider_token=chosen["token"] if isinstance(chosen["token"], str) else None,
            expiry=chosen["expiry"], strike=None, option_type=None,
            lot_size=lot, tick_size=tick,
            metadata_status=meta_status,
            metadata_source=meta_source,
            resolved_at=as_of_dt,
            warnings=warns,
        )

    def _resolve_future_mcx(self, market, as_of_dt, requested_expiry):
        seg = _MARKET_SEGMENTS[market.symbol]["derivative"]
        idx = self._require_index(seg)
        candidates = []
        for r in idx.records:
            if r.instrument_kind != "FUTURE":
                continue
            if (r.underlying_symbol or "").upper() != market.symbol:
                # fall back to symbol-prefix match
                if not r.symbol.upper().endswith(market.symbol + "FUT") and \
                   not r.symbol.upper().startswith(market.symbol):
                    continue
            if r.expiry is None or r.expiry <= as_of_dt.date():
                continue
            if requested_expiry is not None and r.expiry != requested_expiry:
                continue
            candidates.append(r)
        if not candidates:
            raise FyersResolutionError(
                f"no non-expired MCX futures for {market.symbol}"
                + (f" at expiry {requested_expiry}" if requested_expiry else "")
            )
        nearest_expiry = min(r.expiry for r in candidates)
        nearest = [r for r in candidates if r.expiry == nearest_expiry]
        if len(nearest) > 1:
            distinct = {r.symbol for r in nearest}
            if len(distinct) > 1:
                raise FyersResolutionError(
                    f"ambiguous MCX futures for {market.symbol} at {nearest_expiry}"
                )
        rec = nearest[0]
        meta_status, lot, tick, meta_source, warns = self._classify_metadata_rec(rec)
        return self._build(
            market=market,
            instrument_type="FUTURE",
            provider_symbol=rec.symbol,
            provider_exchange=rec.exchange,
            provider_token=rec.provider_token,
            expiry=rec.expiry, strike=None, option_type=None,
            lot_size=lot, tick_size=tick,
            metadata_status=meta_status,
            metadata_source=meta_source,
            resolved_at=as_of_dt,
            warnings=warns,
        )

    # ---------- OPTION ----------

    def _resolve_option(self, market, as_of_dt, expiry, strike, option_type):
        if not isinstance(expiry, date):
            raise FyersResolutionError("OPTION expiry must be a date")
        if expiry <= as_of_dt.date():
            raise FyersResolutionError(
                f"OPTION expiry {expiry} is not in the future"
            )
        ot = option_type.upper().strip()
        if ot not in _VALID_OPTION_TYPES:
            raise FyersResolutionError(f"invalid option_type: {option_type!r}")
        if not (isinstance(strike, float) and strike > 0) and \
           not (isinstance(strike, int) and strike > 0):
            raise FyersResolutionError(f"invalid strike: {strike!r}")

        seg = _MARKET_SEGMENTS[market.symbol]["derivative"]
        idx = self._require_index(seg)
        candidates = [
            r for r in idx.records
            if r.instrument_kind == "OPTION"
            and r.expiry == expiry
            and r.option_type == ot
            and r.strike is not None
            and abs(r.strike - float(strike)) <= 1e-6
            and (
                (r.underlying_symbol or "").upper() == market.symbol
                or r.symbol.upper().startswith(market.symbol)
            )
        ]
        if not candidates:
            raise FyersResolutionError(
                f"no option for {market.symbol} {expiry} {strike} {ot}"
            )
        if len(candidates) > 1:
            distinct = {r.symbol for r in candidates}
            if len(distinct) > 1:
                raise FyersResolutionError(
                    f"ambiguous option identity for "
                    f"{market.symbol} {expiry} {strike} {ot}"
                )
        rec = candidates[0]
        if not rec.provider_token and rec.lot_size is None:
            # Still allowed; but warn
            pass
        meta_status, lot, tick, meta_source, warns = self._classify_metadata_rec(rec)
        return self._build(
            market=market,
            instrument_type="OPTION",
            provider_symbol=rec.symbol,
            provider_exchange=rec.exchange,
            provider_token=rec.provider_token,
            expiry=rec.expiry, strike=rec.strike, option_type=rec.option_type,
            lot_size=lot, tick_size=tick,
            metadata_status=meta_status,
            metadata_source=meta_source,
            resolved_at=as_of_dt,
            warnings=warns,
        )

    # ---------- helpers ----------

    def _require_index(self, segment: str) -> FyersSymbolMasterIndexV2:
        if segment not in SUPPORTED_SEGMENTS:
            raise FyersResolutionError(f"unsupported segment: {segment}")
        try:
            return self._store.get_index(segment)
        except FyersResolutionError:
            raise
        except FyersSymbolMasterError as exc:
            raise FyersResolutionError(
                f"master unavailable for {segment}: {exc}"
            ) from exc
        except Exception as exc:
            # Any store-level failure must fail closed with the F8 error
            # type so callers cannot silently catch a narrower RuntimeError.
            raise FyersResolutionError(
                f"master store error for {segment}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    @staticmethod
    def _classify_metadata(row: Mapping):
        lot = row.get("lot")
        tick = row.get("tick")
        lot_i = int(lot) if isinstance(lot, (int, float)) and lot and lot > 0 else None
        tick_f = float(tick) if isinstance(tick, (int, float)) and tick and tick > 0 else None
        if lot_i is None or tick_f is None:
            return "UNAVAILABLE", None, None, None, ("metadata_incomplete",)
        return "VERIFIED", lot_i, tick_f, "fyers_symbol_master", ()

    @staticmethod
    def _classify_metadata_rec(rec: FyersMasterRecordV2):
        if rec.lot_size is None or rec.tick_size is None:
            return "UNAVAILABLE", None, None, None, ("metadata_incomplete",)
        return "VERIFIED", rec.lot_size, rec.tick_size, "fyers_symbol_master", ()

    def _build(self, *, market, instrument_type, provider_symbol,
               provider_exchange, provider_token, expiry, strike, option_type,
               lot_size, tick_size, metadata_status, metadata_source,
               resolved_at, warnings):
        rid = _canonical_resolution_id(
            market.symbol, instrument_type, provider_symbol,
            expiry, strike, option_type,
        )
        canonical_id = self._canonical_id(
            market.symbol, instrument_type, expiry, strike, option_type
        )
        ri = ResolvedInstrumentV2(
            resolution_id=rid,
            provider="FYERS",
            market_symbol=market.symbol,
            market_type=market.market_type,
            underlying_exchange=market.underlying_exchange,
            derivative_exchange=market.derivative_exchange,
            instrument_type=instrument_type,
            canonical_instrument_id=canonical_id,
            provider_symbol=provider_symbol,
            provider_exchange=provider_exchange,
            provider_token=provider_token,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size,
            tick_size=tick_size,
            contract_metadata_status=metadata_status,
            metadata_source=metadata_source,
            resolved_at=resolved_at,
            warnings=tuple(warnings or ()),
        )
        return ri.to_provider_instrument()

    @staticmethod
    def _canonical_id(market_symbol, instrument_type, expiry, strike, option_type) -> str:
        parts = [market_symbol, instrument_type]
        if expiry is not None:
            parts.append(expiry.isoformat())
        if strike is not None:
            parts.append("%.4f" % strike)
        if option_type is not None:
            parts.append(option_type.upper())
        return ":".join(parts)
