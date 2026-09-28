"""F15-R2 Phase R2-3 — trade identity tests."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from trade_identity import (  # noqa: E402
    is_legacy_trade_id,
    make_trade_id,
    parse_trade_id,
)

IST = timezone(timedelta(hours=5, minutes=30))
FROZEN = datetime(2026, 9, 29, 10, 15, 22, 123456, tzinfo=IST)


# ---------------- prefix selection ----------------

def test_index_prefix_is_TRD():
    tid = make_trade_id("NIFTY", now=FROZEN)
    assert tid.startswith("TRD_NIFTY_")


def test_sensex_prefix_is_TRD():
    tid = make_trade_id("SENSEX", now=FROZEN)
    assert tid.startswith("TRD_SENSEX_")


def test_mcx_prefix_is_MCX():
    for m in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        assert make_trade_id(m, now=FROZEN).startswith(f"MCX_{m}_")


def test_unknown_market_rejected():
    with pytest.raises(ValueError):
        make_trade_id("BANKNIFTY", now=FROZEN)


def test_empty_market_rejected():
    with pytest.raises(ValueError):
        make_trade_id("", now=FROZEN)


# ---------------- cross-market collision protection ----------------

def test_same_timestamp_nifty_vs_sensex_differ():
    a = make_trade_id("NIFTY", now=FROZEN)
    b = make_trade_id("SENSEX", now=FROZEN)
    assert a != b


def test_same_timestamp_crudeoil_vs_goldm_differ():
    a = make_trade_id("CRUDEOILM", now=FROZEN)
    b = make_trade_id("GOLDM", now=FROZEN)
    assert a != b


# ---------------- subsecond uniqueness ----------------

def test_rapid_consecutive_same_market_differ():
    a = make_trade_id("NIFTY", now=FROZEN)
    b = make_trade_id("NIFTY", now=FROZEN.replace(microsecond=FROZEN.microsecond + 1))
    assert a != b


def test_microsecond_precision_present():
    tid = make_trade_id("NIFTY", now=FROZEN)
    # Canonical form: PREFIX_MARKET_YYYYMMDD_HHMMSSffffff (4 parts).
    # The timestamp itself contains an underscore, so the id splits
    # into [prefix, market, date, time+micros].
    parts = tid.split("_")
    assert len(parts) == 4
    assert parts[0] == "TRD"
    assert parts[1] == "NIFTY"
    assert parts[2] == "20260929"
    assert parts[3] == "101522123456"  # HHMMSSffffff
    assert tid.endswith("123456")


# ---------------- legacy compatibility ----------------

def test_legacy_trd_id_is_legacy():
    assert is_legacy_trade_id("TRD_20260928_095648") is True


def test_legacy_mcx_id_is_legacy():
    assert is_legacy_trade_id("MCX_20260928_095648") is True


def test_canonical_id_is_not_legacy():
    assert is_legacy_trade_id("TRD_NIFTY_20260929_101522123456") is False
    assert is_legacy_trade_id("MCX_GOLDM_20260929_101522123456") is False


def test_parse_legacy_returns_none_market():
    assert parse_trade_id("TRD_20260928_095648") == (None, "TRD_20260928_095648")
    assert parse_trade_id("MCX_20260928_095648") == (None, "MCX_20260928_095648")


def test_parse_canonical_returns_market():
    a = parse_trade_id("TRD_NIFTY_20260929_101522123456")
    assert a == ("NIFTY", "TRD_NIFTY_20260929_101522123456")
    b = parse_trade_id("MCX_GOLDM_20260929_101522123456")
    assert b == ("GOLDM", "MCX_GOLDM_20260929_101522123456")


def test_parse_garbage_returns_none_market():
    for bad in ("", None, "random", "TRD_", "TRD_X", 42):
        m, t = parse_trade_id(bad)
        assert m is None


def test_parse_canonical_wrong_prefix_rejected():
    # underscore-count is right but prefix is not TRD/MCX
    m, _ = parse_trade_id("XYZ_NIFTY_20260929_101522123456")
    assert m is None


# ---------------- make/parse round-trip ----------------

def test_make_then_parse_round_trip_index():
    tid = make_trade_id("NIFTY", now=FROZEN)
    m, t = parse_trade_id(tid)
    assert m == "NIFTY"
    assert t == tid
    assert is_legacy_trade_id(tid) is False


def test_make_then_parse_round_trip_mcx():
    tid = make_trade_id("NATGASMINI", now=FROZEN)
    m, t = parse_trade_id(tid)
    assert m == "NATGASMINI"
    assert t == tid
    assert is_legacy_trade_id(tid) is False
