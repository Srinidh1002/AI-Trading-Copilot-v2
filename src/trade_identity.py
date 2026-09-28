"""Canonical PAPER trade identity — F15-R2 Phase R2-3.

Market-scoped, subsecond-precision trade IDs. Replaces two independent
time-only generators that could collide across markets:

    index  src/target_focused_bot.py:1823  -> TRD_YYYYMMDD_HHMMSS
    mcx    src/mcx/mcx_paper_bot.py:712    -> MCX_YYYYMMDD_HHMMSS

New canonical form:

    TRD_<MARKET>_<YYYYMMDD_HHMMSSffffff>     NIFTY / SENSEX
    MCX_<PRODUCT>_<YYYYMMDD_HHMMSSffffff>    CRUDEOILM / GOLDM / NATGASMINI

Legacy IDs (TRD_YYYYMMDD_HHMMSS, MCX_YYYYMMDD_HHMMSS) remain readable
via parse_trade_id(), which returns (None, tid) for the legacy form.
No code in the repo today splits on underscores, so legacy IDs stay
opaque everywhere. This module exists so any future cross-market
reasoning has a canonical (market, trade_id) pair it can rely on.

No certification, counter, or state access. Pure string utilities.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

_INDEX_MARKETS = ("NIFTY", "SENSEX")
_MCX_MARKETS = ("CRUDEOILM", "GOLDM", "NATGASMINI")

# Underscore-separated parts: legacy = 3 (prefix, date, time),
# canonical = 4 (prefix, market, date, time).
#
# Note: the timestamp format YYYYMMDD_HHMMSSffffff contains an
# internal underscore, so a canonical id splits into 4 pieces.
_LEGACY_PARTS = 3
_CANONICAL_PARTS = 4
_KNOWN_PREFIXES = ("TRD", "MCX")


def make_trade_id(market, now=None):
    """Return a market-scoped, subsecond trade ID for `market`.

    Format:
        TRD_<MARKET>_<YYYYMMDD_HHMMSSffffff>   NIFTY / SENSEX
        MCX_<PRODUCT>_<YYYYMMDD_HHMMSSffffff>  CRUDEOILM / GOLDM / NATGASMINI
    """
    if not market:
        raise ValueError("market is required")
    m = str(market).upper().strip()
    if m in _MCX_MARKETS:
        prefix = "MCX"
    elif m in _INDEX_MARKETS:
        prefix = "TRD"
    else:
        raise ValueError(f"unknown market for trade identity: {market!r}")
    dt = now or datetime.now(IST)
    ts = dt.strftime("%Y%m%d_%H%M%S%f")
    return f"{prefix}_{m}_{ts}"


def is_legacy_trade_id(tid):
    """True when `tid` uses the pre-F15-R2 time-only form.

    Legacy: PREFIX_YYYYMMDD_HHMMSS       (3 underscore-separated parts)
    Canonical: PREFIX_MARKET_YYYYMMDD_HHMMSSffffff (4 parts)
    """
    if not isinstance(tid, str) or not tid:
        return False
    parts = tid.split("_")
    return len(parts) == _LEGACY_PARTS and parts[0] in _KNOWN_PREFIXES


def parse_trade_id(tid):
    """Return (market_or_None, tid).

    (None, tid)          legacy form or unparsable
    (MARKET, tid)        canonical form
    """
    if not isinstance(tid, str) or not tid:
        return (None, tid)
    parts = tid.split("_")
    if len(parts) == _CANONICAL_PARTS and parts[0] in _KNOWN_PREFIXES:
        return (parts[1].upper(), tid)
    return (None, tid)
