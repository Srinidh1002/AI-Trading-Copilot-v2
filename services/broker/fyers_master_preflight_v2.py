"""Read-only FYERS symbol-master preflight authority for the five-market PAPER runtime.

This gate exists to prevent a clean deployment from reporting READY when the
provider resolver's required per-segment caches were not packaged. It never
downloads, rewrites, or repairs master data; provisioning remains an explicit
release step.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterIndexV2,
    FyersSymbolMasterError,
)

DEFAULT_MAX_AGE_DAYS = 30

_MARKET_SEGMENT = {
    "NIFTY": "NSE_FO",
    "SENSEX": "BSE_FO",
    "CRUDEOILM": "MCX_COM",
    "GOLDM": "MCX_COM",
    "NATGASMINI": "MCX_COM",
}


def _parse_retrieved_at(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # Historical caches may serialize a locale-style timestamp.
        for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _market_record_matches(record, market: str) -> bool:
    market = market.upper()
    underlying = (record.underlying_symbol or "").upper()
    symbol = record.symbol.upper()

    if market == "NIFTY":
        return underlying == "NIFTY" or (
            symbol.startswith("NSE:NIFTY") and "BANKNIFTY" not in symbol and "FINNIFTY" not in symbol
        )
    if market == "SENSEX":
        return underlying == "SENSEX" or (
            symbol.startswith("BSE:SENSEX") and "SENSEX50" not in symbol
        )
    return underlying == market or market in symbol


def _has_tradable_derivative(index: FyersSymbolMasterIndexV2, market: str, as_of: date) -> bool:
    for record in index.records:
        if record.instrument_kind not in {"OPTION", "FUTURE"}:
            continue
        if record.expiry is None or record.expiry < as_of:
            continue
        if _market_record_matches(record, market):
            return True
    return False


def check_fyers_master_authority_v2(
    repo_root: str | Path,
    markets: Iterable[str],
    *,
    now: datetime | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, tuple[bool, str]]:
    """Return one fail-closed verdict per requested market.

    Required cache mapping:
      NIFTY      -> NSE_FO.json
      SENSEX     -> BSE_FO.json
      all MCX    -> MCX_COM.json

    Validation is read-only and checks:
      * file exists and JSON is readable;
      * payload segment matches the required segment;
      * rows are non-empty and parse into at least one valid record;
      * retrieval timestamp exists and is not older than max_age_days;
      * the requested market has at least one non-expired OPTION/FUTURE identity.
    """
    root = Path(repo_root).resolve()
    base = root / "data" / "provider_cache" / "fyers_master"
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = now_utc.date()

    out: dict[str, tuple[bool, str]] = {}
    segment_cache: dict[str, tuple[bool, str, FyersSymbolMasterIndexV2 | None]] = {}

    for raw_market in markets:
        market = str(raw_market or "").strip().upper()
        segment = _MARKET_SEGMENT.get(market)
        if segment is None:
            out[market] = (False, "FYERS_MASTER_UNSUPPORTED_MARKET")
            continue

        if segment not in segment_cache:
            path = base / f"{segment}.json"
            if not path.is_file():
                segment_cache[segment] = (
                    False,
                    f"FYERS_MASTER_MISSING:{segment}",
                    None,
                )
            else:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    segment_cache[segment] = (
                        False,
                        f"FYERS_MASTER_UNREADABLE:{segment}:{type(exc).__name__}",
                        None,
                    )
                else:
                    if not isinstance(payload, dict):
                        segment_cache[segment] = (
                            False,
                            f"FYERS_MASTER_SCHEMA_INVALID:{segment}",
                            None,
                        )
                    elif str(payload.get("segment") or "").upper() != segment:
                        segment_cache[segment] = (
                            False,
                            f"FYERS_MASTER_SEGMENT_MISMATCH:{segment}",
                            None,
                        )
                    else:
                        rows = payload.get("rows")
                        if not isinstance(rows, list) or not rows:
                            segment_cache[segment] = (
                                False,
                                f"FYERS_MASTER_EMPTY:{segment}",
                                None,
                            )
                        else:
                            retrieved_at = _parse_retrieved_at(payload.get("retrieved_at"))
                            if retrieved_at is None:
                                segment_cache[segment] = (
                                    False,
                                    f"FYERS_MASTER_RETRIEVED_AT_INVALID:{segment}",
                                    None,
                                )
                            else:
                                age_days = (now_utc - retrieved_at).total_seconds() / 86400.0
                                if age_days < -1:
                                    segment_cache[segment] = (
                                        False,
                                        f"FYERS_MASTER_TIMESTAMP_FUTURE:{segment}",
                                        None,
                                    )
                                elif age_days > max_age_days:
                                    segment_cache[segment] = (
                                        False,
                                        f"FYERS_MASTER_STALE:{segment}:age_days={age_days:.1f}",
                                        None,
                                    )
                                else:
                                    try:
                                        idx = FyersSymbolMasterIndexV2.from_rows(
                                            rows,
                                            segment=segment,
                                        )
                                    except FyersSymbolMasterError as exc:
                                        segment_cache[segment] = (
                                            False,
                                            f"FYERS_MASTER_PARSE_FAILED:{segment}:{type(exc).__name__}",
                                            None,
                                        )
                                    else:
                                        if not idx.records:
                                            segment_cache[segment] = (
                                                False,
                                                f"FYERS_MASTER_NO_VALID_RECORDS:{segment}",
                                                None,
                                            )
                                        else:
                                            segment_cache[segment] = (
                                                True,
                                                f"segment={segment}|records={len(idx.records)}|age_days={age_days:.1f}",
                                                idx,
                                            )

        seg_ok, seg_reason, idx = segment_cache[segment]
        if not seg_ok or idx is None:
            out[market] = (False, seg_reason)
            continue

        if not _has_tradable_derivative(idx, market, today):
            out[market] = (
                False,
                f"FYERS_MASTER_NO_CURRENT_DERIVATIVE:{segment}:{market}",
            )
            continue

        out[market] = (True, seg_reason)

    return out
