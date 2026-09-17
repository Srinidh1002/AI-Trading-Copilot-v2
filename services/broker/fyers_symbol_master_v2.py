"""FYERS public symbol-master reader, parser and cache (F8).

Deterministic, offline-testable view of FYERS instrument masters for the
five-market universe. Performs no auth, no network, no order operations.
Caching is atomic. Parser is schema-tolerant and never relies on a single
field to classify instrument kind.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

SUPPORTED_SEGMENTS = ("NSE_CM", "NSE_FO", "BSE_CM", "BSE_FO", "MCX_COM")
_INSTRUMENT_KINDS = ("UNDERLYING", "FUTURE", "OPTION")

_SYMBOL_KEYS = ("symbol", "fy_symbol", "prov_symbol", "provider_symbol")
_EXCHANGE_KEYS = ("exch", "exchange", "provider_exchange")
_SEGMENT_KEYS = ("segment", "fy_segment", "exch_segment")
_INSTRUMENT_TYPE_KEYS = ("instrument_type", "instr_type", "type", "inst_type", "series")
_UNDERLYING_KEYS = ("underlying_symbol", "underlying", "root", "underlying_sym")
_TOKEN_KEYS = ("fyToken", "fy_token", "token", "symbolToken")
_EXPIRY_KEYS = ("expiry", "expiry_date", "expiryDate")
_STRIKE_KEYS = ("strike", "strike_price", "strikePrice")
_OPTION_TYPE_KEYS = ("option_type", "opt_type", "optType", "optionType")
_LOT_KEYS = ("lot_size", "lotSize", "lot")
_TICK_KEYS = ("tick_size", "tickSize", "tick")

_FUT_HINTS = ("FUT", "FUTURE", "FUTURES")
_OPT_HINTS = ("OPT", "OPTION", "OPTIONS")
_IDX_HINTS = ("INDEX", "IDX", "SPOT")
_EQ_HINTS = ("EQ", "EQUITY")
_COMM_HINTS = ("COMMODITY", "COMM")

_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


class FyersSymbolMasterError(RuntimeError):
    """F8 master layer failed closed."""


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip()
    return v or None


def _upper(value: object) -> str | None:
    t = _text(value)
    return t.upper() if t else None


def _pos_int(value: object) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _pos_float(value: object) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")) or f <= 0:
        return None
    return f


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    m = _ISO_RE.match(v)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    for fmt, ln in (("%d%b%Y", 9), ("%d%b%y", 7)):
        try:
            return datetime.strptime(v[:ln], fmt).date()
        except ValueError:
            continue
    return None


def _pick(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _classify_kind(instrument_type_raw, expiry, strike, option_type) -> str | None:
    """Schema-driven classification for FYERS public master rows.

    The CSV `strike_or_ref` field (index 14) is non-zero for cash rows
    and for futures; it is NOT a strike. Classification must be driven
    by expiry + optType presence:

      optType in {CE,PE} + expiry + positive strike -> OPTION
      expiry present, optType not CE/PE             -> FUTURE
      no expiry and no CE/PE optType                -> UNDERLYING
    """
    it = _upper(instrument_type_raw) or ""

    if option_type in ("CE", "PE"):
        if expiry is not None and strike is not None and strike > 0:
            return "OPTION"
        return None

    if expiry is not None:
        return "FUTURE"

    # No expiry, no CE/PE optType -> underlying (index, commodity root,
    # or equity cash).
    if (
        any(h in it for h in _IDX_HINTS)
        or any(h in it for h in _COMM_HINTS)
        or it in ("",)
        or it in _EQ_HINTS
    ):
        return "UNDERLYING"
    return None

@dataclass(frozen=True, slots=True)
class FyersMasterRecordV2:
    symbol: str
    exchange: str
    segment: str
    instrument_kind: str
    underlying_symbol: str | None
    provider_token: str | None
    expiry: date | None
    strike: float | None
    option_type: str | None
    lot_size: int | None
    tick_size: float | None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise FyersSymbolMasterError("symbol required")
        if not self.exchange:
            raise FyersSymbolMasterError("exchange required")
        if self.segment not in SUPPORTED_SEGMENTS:
            raise FyersSymbolMasterError(f"unsupported segment: {self.segment}")
        if self.instrument_kind not in _INSTRUMENT_KINDS:
            raise FyersSymbolMasterError(f"unsupported kind: {self.instrument_kind}")
        if self.instrument_kind == "OPTION":
            if self.option_type not in ("CE", "PE"):
                raise FyersSymbolMasterError("option requires CE or PE")
            if self.strike is None or self.expiry is None:
                raise FyersSymbolMasterError("option requires strike and expiry")
        elif self.instrument_kind == "FUTURE":
            if self.expiry is None or self.strike is not None or self.option_type is not None:
                raise FyersSymbolMasterError("future requires expiry; no strike/opt")
        elif self.instrument_kind == "UNDERLYING":
            if self.expiry is not None or self.strike is not None or self.option_type is not None:
                raise FyersSymbolMasterError("underlying has no derivative fields")


def parse_master_record_v2(row, *, default_segment: str) -> FyersMasterRecordV2 | None:
    if not isinstance(row, Mapping):
        return None
    symbol = _text(_pick(row, _SYMBOL_KEYS))
    if not symbol:
        return None
    exchange = _upper(_pick(row, _EXCHANGE_KEYS))
    if not exchange and ":" in symbol:
        exchange = symbol.split(":", 1)[0].upper()
    if not exchange:
        return None
    seg = _upper(_pick(row, _SEGMENT_KEYS)) or default_segment
    if seg not in SUPPORTED_SEGMENTS:
        return None

    raw_opt = _upper(_pick(row, _OPTION_TYPE_KEYS))
    opt = raw_opt if raw_opt in ("CE", "PE") else None
    expiry = _parse_date(_pick(row, _EXPIRY_KEYS))
    strike = _pos_float(_pick(row, _STRIKE_KEYS))

    kind = _classify_kind(
        _pick(row, _INSTRUMENT_TYPE_KEYS), expiry, strike, opt
    )
    if kind is None:
        return None

    # Schema-driven normalization: FUTURE / UNDERLYING must not carry
    # strike or optType; UNDERLYING must not carry expiry either. This
    # prevents the CSV `strike_or_ref` field (which is non-zero for
    # cash rows and futures) from leaking into derivative fields.
    if kind == "FUTURE":
        strike = None
        opt = None
    elif kind == "UNDERLYING":
        expiry = None
        strike = None
        opt = None

    try:
        return FyersMasterRecordV2(
            symbol=symbol,
            exchange=exchange,
            segment=seg,
            instrument_kind=kind,
            underlying_symbol=_upper(_pick(row, _UNDERLYING_KEYS)),
            provider_token=_text(_pick(row, _TOKEN_KEYS)),
            expiry=expiry,
            strike=strike,
            option_type=opt,
            lot_size=_pos_int(_pick(row, _LOT_KEYS)),
            tick_size=_pos_float(_pick(row, _TICK_KEYS)),
        )
    except FyersSymbolMasterError:
        return None


@dataclass(frozen=True, slots=True)
class FyersSymbolMasterIndexV2:
    segment: str
    records: tuple[FyersMasterRecordV2, ...]
    malformed_rows: int

    @classmethod
    def from_rows(cls, rows, segment: str) -> "FyersSymbolMasterIndexV2":
        if segment not in SUPPORTED_SEGMENTS:
            raise FyersSymbolMasterError(f"unsupported segment: {segment}")
        recs = []
        bad = 0
        for r in rows or ():
            rec = parse_master_record_v2(r, default_segment=segment)
            if rec is None:
                bad += 1
            else:
                recs.append(rec)
        return cls(segment=segment, records=tuple(recs), malformed_rows=bad)

    def find(self, *, kind=None, underlying=None, expiry=None, strike=None,
             option_type=None, exchange=None) -> list[FyersMasterRecordV2]:
        out = []
        for r in self.records:
            if kind and r.instrument_kind != kind:
                continue
            if underlying is not None and (r.underlying_symbol or "").upper() != underlying.upper():
                continue
            if expiry is not None and r.expiry != expiry:
                continue
            if strike is not None and (r.strike is None or abs(r.strike - strike) > 1e-6):
                continue
            if option_type is not None and r.option_type != option_type.upper():
                continue
            if exchange is not None and r.exchange != exchange.upper():
                continue
            out.append(r)
        return out


class FyersSymbolMasterStoreV2:
    """File-backed, per-segment, atomic-replacement master cache."""

    def __init__(self, base_dir: str = "data/provider_cache/fyers_master") -> None:
        self._base_dir = str(base_dir)
        self._cache: dict[str, FyersSymbolMasterIndexV2] = {}

    def path_for(self, segment: str) -> str:
        if segment not in SUPPORTED_SEGMENTS:
            raise FyersSymbolMasterError(f"unsupported segment: {segment}")
        return os.path.join(self._base_dir, f"{segment}.json")

    def get_index(self, segment: str) -> FyersSymbolMasterIndexV2:
        if segment in self._cache:
            return self._cache[segment]
        p = self.path_for(segment)
        if not os.path.isfile(p):
            raise FyersSymbolMasterError(
                f"master not cached for segment {segment}: {p}"
            )
        try:
            with open(p, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            raise FyersSymbolMasterError(
                f"master cache unreadable for {segment}: {exc}"
            ) from exc
        if not isinstance(payload, Mapping) or "rows" not in payload:
            raise FyersSymbolMasterError(f"master cache malformed for {segment}")
        idx = FyersSymbolMasterIndexV2.from_rows(
            payload.get("rows") or (), segment=segment
        )
        self._cache[segment] = idx
        return idx

    def save(self, segment: str, rows) -> None:
        p = self.path_for(segment)
        os.makedirs(self._base_dir, exist_ok=True)
        payload = {
            "segment": segment,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "rows": list(rows),
        }
        fd, tmp = tempfile.mkstemp(
            prefix=os.path.basename(p) + ".", dir=os.path.dirname(p)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, separators=(",", ":"))
            os.replace(tmp, p)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._cache.pop(segment, None)
