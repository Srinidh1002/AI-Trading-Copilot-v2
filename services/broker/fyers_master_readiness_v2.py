"""R16 FYERS symbol-master readiness and atomic runtime provisioning.

This module is intentionally data-only and state-neutral. It validates the
cached FYERS derivative masters required by the five-market PAPER runtime and
can explicitly copy a verified cache from a trusted release/source directory
into a target runtime using atomic replacement.

It never authenticates, calls FYERS, mutates certification state, or enables
broker/live execution.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path

from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterError,
    FyersSymbolMasterIndexV2,
)

MARKET_SEGMENT_V2 = {
    "NIFTY": "NSE_FO",
    "SENSEX": "BSE_FO",
    "CRUDEOILM": "MCX_COM",
    "GOLDM": "MCX_COM",
    "NATGASMINI": "MCX_COM",
}

INDEX_MARKETS_V2 = frozenset({"NIFTY", "SENSEX"})
MCX_MARKETS_V2 = frozenset({"CRUDEOILM", "GOLDM", "NATGASMINI"})


class FyersMasterReadinessError(RuntimeError):
    """Required FYERS master evidence is absent or invalid."""


def required_segments_for_markets(markets: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in markets:
        market = str(raw or "").strip().upper()
        segment = MARKET_SEGMENT_V2.get(market)
        if segment is None:
            raise FyersMasterReadinessError(f"UNSUPPORTED_MARKET:{market or raw!r}")
        if segment not in seen:
            seen.add(segment)
            ordered.append(segment)
    return tuple(ordered)


def _master_path(base_dir: str | os.PathLike[str], segment: str) -> Path:
    return Path(base_dir) / f"{segment}.json"


def _load_payload(path: Path, expected_segment: str) -> tuple[Mapping, FyersSymbolMasterIndexV2]:
    if not path.is_file():
        raise FyersMasterReadinessError(f"MASTER_MISSING:{expected_segment}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FyersMasterReadinessError(
            f"MASTER_UNREADABLE:{expected_segment}:{type(exc).__name__}"
        ) from exc

    if not isinstance(payload, Mapping):
        raise FyersMasterReadinessError(f"MASTER_SCHEMA_INVALID:{expected_segment}")

    segment = str(payload.get("segment") or "").strip().upper()
    if segment != expected_segment:
        raise FyersMasterReadinessError(
            f"MASTER_SEGMENT_MISMATCH:{expected_segment}:{segment or 'NONE'}"
        )

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise FyersMasterReadinessError(f"MASTER_ROWS_EMPTY:{expected_segment}")

    try:
        index = FyersSymbolMasterIndexV2.from_rows(rows, segment=expected_segment)
    except FyersSymbolMasterError as exc:
        raise FyersMasterReadinessError(
            f"MASTER_PARSE_FAILED:{expected_segment}:{type(exc).__name__}"
        ) from exc

    if not index.records:
        raise FyersMasterReadinessError(f"MASTER_NO_VALID_RECORDS:{expected_segment}")

    return payload, index


def _matches_market(record, market: str) -> bool:
    underlying = str(record.underlying_symbol or "").strip().upper()
    symbol = str(record.symbol or "").strip().upper()

    if underlying == market:
        return True

    if market == "NIFTY":
        return symbol.startswith("NSE:NIFTY") and not symbol.startswith(
            ("NSE:BANKNIFTY", "NSE:FINNIFTY")
        )
    if market == "SENSEX":
        return symbol.startswith("BSE:SENSEX") and not symbol.startswith(
            "BSE:SENSEX50"
        )
    return market in MCX_MARKETS_V2 and (
        symbol.startswith(f"MCX:{market}") or symbol.startswith(market)
    )


def _market_contract_readiness(
    index: FyersSymbolMasterIndexV2,
    market: str,
    as_of: date,
) -> tuple[bool, str]:
    records = [r for r in index.records if _matches_market(r, market)]

    if market in INDEX_MARKETS_V2:
        options = [
            r
            for r in records
            if r.instrument_kind == "OPTION"
            and r.expiry is not None
            and r.expiry >= as_of
            and r.option_type in {"CE", "PE"}
            and r.strike is not None
        ]
        expiries = sorted({r.expiry for r in options if r.expiry is not None})
        if not options:
            return False, "MASTER_NO_CURRENT_INDEX_OPTIONS"
        return True, (
            f"segment={index.segment}|records={len(records)}|"
            f"options={len(options)}|next_expiry={expiries[0].isoformat()}"
        )

    futures = [
        r
        for r in records
        if r.instrument_kind == "FUTURE"
        and r.expiry is not None
        and r.expiry >= as_of
    ]
    options = [
        r
        for r in records
        if r.instrument_kind == "OPTION"
        and r.expiry is not None
        and r.expiry >= as_of
        and r.option_type in {"CE", "PE"}
        and r.strike is not None
    ]
    if not futures:
        return False, "MASTER_NO_CURRENT_MCX_FUTURES"
    if not options:
        return False, "MASTER_NO_CURRENT_MCX_OPTIONS"
    next_future = min(r.expiry for r in futures if r.expiry is not None)
    next_option = min(r.expiry for r in options if r.expiry is not None)
    return True, (
        f"segment={index.segment}|records={len(records)}|"
        f"futures={len(futures)}|options={len(options)}|"
        f"next_future={next_future.isoformat()}|next_option={next_option.isoformat()}"
    )


def audit_required_master_cache(
    *,
    repo_root: str | os.PathLike[str],
    markets: Iterable[str],
    as_of: date | datetime | None = None,
) -> dict[str, tuple[bool, str]]:
    """Return per-market read-only readiness verdicts for required masters."""

    root = Path(repo_root).resolve()
    base_dir = root / "data" / "provider_cache" / "fyers_master"

    if isinstance(as_of, datetime):
        as_of_date = as_of.date()
    elif isinstance(as_of, date):
        as_of_date = as_of
    else:
        as_of_date = datetime.now().date()

    requested = tuple(str(m).strip().upper() for m in markets)
    loaded: dict[str, FyersSymbolMasterIndexV2] = {}
    load_errors: dict[str, str] = {}

    for segment in required_segments_for_markets(requested):
        try:
            _payload, index = _load_payload(_master_path(base_dir, segment), segment)
            loaded[segment] = index
        except FyersMasterReadinessError as exc:
            load_errors[segment] = str(exc)

    out: dict[str, tuple[bool, str]] = {}
    for market in requested:
        segment = MARKET_SEGMENT_V2[market]
        if segment in load_errors:
            out[market] = (False, load_errors[segment])
            continue
        index = loaded.get(segment)
        if index is None:
            out[market] = (False, f"MASTER_INTERNAL_MISSING:{segment}")
            continue
        out[market] = _market_contract_readiness(index, market, as_of_date)
    return out


def sync_required_master_cache(
    *,
    repo_root: str | os.PathLike[str],
    source_dir: str | os.PathLike[str],
    markets: Iterable[str],
    as_of: date | datetime | None = None,
) -> dict[str, str]:
    """Atomically install only validated required segment caches.

    The entire source set is validated for all requested markets before the
    first target file is replaced. This prevents a partially validated source
    directory from being installed.
    """

    root = Path(repo_root).resolve()
    source = Path(source_dir).resolve()
    target = root / "data" / "provider_cache" / "fyers_master"
    requested = tuple(str(m).strip().upper() for m in markets)
    segments = required_segments_for_markets(requested)

    if not source.is_dir():
        raise FyersMasterReadinessError(f"MASTER_SOURCE_DIR_MISSING:{source}")

    # Validate source payloads and market coverage before mutating target.
    source_indexes: dict[str, FyersSymbolMasterIndexV2] = {}
    source_paths: dict[str, Path] = {}
    for segment in segments:
        path = _master_path(source, segment)
        _payload, index = _load_payload(path, segment)
        source_indexes[segment] = index
        source_paths[segment] = path

    if isinstance(as_of, datetime):
        as_of_date = as_of.date()
    elif isinstance(as_of, date):
        as_of_date = as_of
    else:
        as_of_date = datetime.now().date()

    for market in requested:
        segment = MARKET_SEGMENT_V2[market]
        ok, reason = _market_contract_readiness(
            source_indexes[segment], market, as_of_date
        )
        if not ok:
            raise FyersMasterReadinessError(
                f"MASTER_SOURCE_NOT_READY:{market}:{reason}"
            )

    target.mkdir(parents=True, exist_ok=True)
    installed: dict[str, str] = {}

    for segment in segments:
        src = source_paths[segment]
        dst = _master_path(target, segment)

        fd, temporary = tempfile.mkstemp(
            prefix=f".{segment}.",
            suffix=".r16tmp",
            dir=str(target),
        )
        os.close(fd)
        tmp = Path(temporary)

        try:
            shutil.copyfile(src, tmp)
            # Re-validate the exact bytes staged for replacement.
            _load_payload(tmp, segment)
            os.replace(tmp, dst)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        installed[segment] = str(dst)

    return installed