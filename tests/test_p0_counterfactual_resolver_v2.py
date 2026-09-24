"""Part 14 — counterfactual price capture and resolver. Synthetic data only."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from mcx import mcx_counterfactual as cf
from tools import resolve_counterfactuals as resolver


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    cfdir = tmp_path / "counterfactual"
    cfdir.mkdir(parents=True, exist_ok=True)
    resolved = tmp_path / "counterfactual_resolved.jsonl"
    monkeypatch.setattr(cf, "_LOG_DIR", str(cfdir))
    monkeypatch.setattr(resolver, "_CF_DIR", cfdir)
    monkeypatch.setattr(resolver, "_RESOLVED_PATH", resolved)
    return cfdir, resolved


def _chain(atm=1000, ce_ltp=10.0, pe_ltp=12.0, product_step=50, tokens=("CE1", "PE1")):
    return {
        "status": "OK",
        "atm": atm,
        "future_ltp": atm,
        "expiry": "2026-12-31",
        "ce_data": {
            float(atm): {"symbol": "CE_" + str(atm), "token": tokens[0],
                         "ltp": ce_ltp, "bid": ce_ltp - 0.1, "ask": ce_ltp + 0.1,
                         "oi": 10000, "vol": 5000},
        },
        "pe_data": {
            float(atm): {"symbol": "PE_" + str(atm), "token": tokens[1],
                         "ltp": pe_ltp, "bid": pe_ltp - 0.1, "ask": pe_ltp + 0.1,
                         "oi": 12000, "vol": 6000},
        },
    }


def _rej(conf_dir, product, conf, ts_offset_min, token, option_side="CE"):
    """Write one threshold-only rejection to <product>_counterfactual.jsonl."""
    ts = (datetime.now(timezone.utc) - timedelta(minutes=ts_offset_min)).isoformat()
    row = {
        "ts_utc": ts,
        "product": product,
        "confidence": conf,
        "direction": "LONG" if option_side == "CE" else "SHORT",
        "regime": "TREND_UP",
        "blocking_reasons": [],
        "threshold_only": True,
        "signal_price": 1000.0,
        "future_price": 1000.0,
        "expiry": "2026-12-31",
        "dte": 30,
        "option_side": option_side,
        "hypothetical_contract": {
            "symbol": "OPT_" + str(token),
            "token": str(token),
            "strike": 1000,
            "type": option_side,
            "ltp": 10.0,
            "score": 0.9,
        },
        "attempt": 1,
        "resolved": False,
    }
    with open(conf_dir / (product.lower() + "_counterfactual.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def _price(product, ts_offset_min, token, ltp, conf_dir):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=ts_offset_min)).isoformat()
    row = {
        "ts_utc": ts,
        "product": product,
        "attempt": 1,
        "future_ltp": 1000.0,
        "atm": 1000,
        "expiry": "2026-12-31",
        "prices": {
            "1000.0:" + ("CE" if token.startswith("CE") else "PE"): {
                "side": "CE" if token.startswith("CE") else "PE",
                "token": str(token),
                "symbol": "OPT_" + str(token),
                "ltp": float(ltp),
                "bid": float(ltp) - 0.1,
                "ask": float(ltp) + 0.1,
                "oi": 10000,
            }
        },
    }
    with open(conf_dir / (product.lower() + "_prices.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


# ---------- price capture --------------------------------------------------

def test_log_cycle_prices_writes_in_window_contracts(isolated_dirs):
    cfdir, _ = isolated_dirs
    cf.log_cycle_prices("CRUDEOILM", _chain(), attempt=7)
    p = cfdir / "crudeoilm_prices.jsonl"
    assert p.exists()
    row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert row["product"] == "CRUDEOILM"
    assert row["attempt"] == 7
    assert row["atm"] == 1000
    assert "1000.0:CE" in row["prices"]
    assert "1000.0:PE" in row["prices"]
    assert row["prices"]["1000.0:CE"]["side"] == "CE"
    assert row["prices"]["1000.0:PE"]["side"] == "PE"


def test_log_cycle_prices_ignores_bad_chain(isolated_dirs):
    cfdir, _ = isolated_dirs
    cf.log_cycle_prices("CRUDEOILM", {"status": "FAILED"}, attempt=1)
    assert not (cfdir / "crudeoilm_prices.jsonl").exists()


def test_log_cycle_prices_is_per_product(isolated_dirs):
    cfdir, _ = isolated_dirs
    cf.log_cycle_prices("CRUDEOILM", _chain())
    cf.log_cycle_prices("GOLDM", _chain())
    assert (cfdir / "crudeoilm_prices.jsonl").exists()
    assert (cfdir / "goldm_prices.jsonl").exists()


# ---------- resolver -------------------------------------------------------

def test_resolver_t1_first(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 10.0, cfdir)   # entry
    _price("CRUDEOILM", 58, "CE1", 11.5, cfdir)   # +15% T1
    rc = resolver.main(["--products", "CRUDEOILM"])
    assert rc == 0
    rows = [json.loads(l) for l in resolver._RESOLVED_PATH.read_text().splitlines()]
    assert rows[0]["outcome"] == "T1_FIRST"
    assert rows[0]["token"] == "CE1"


def test_resolver_sl_first(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 10.0, cfdir)
    _price("CRUDEOILM", 58, "CE1", 9.0, cfdir)    # -10% < -8% SL
    rc = resolver.main(["--products", "CRUDEOILM"])
    assert rc == 0
    rows = [json.loads(l) for l in resolver._RESOLVED_PATH.read_text().splitlines()]
    assert rows[0]["outcome"] == "SL_FIRST"


def test_resolver_ambiguous_sl_then_t1_same_row(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 10.0, cfdir)
    # one row touches both: not possible for one price, so use two rows
    # at the same timestamp resolution. Use SL then T1 at the exact same ts.
    now = datetime.now(timezone.utc)
    same_ts = (now - timedelta(minutes=58)).isoformat()
    for ltp in (9.0, 11.5):
        with open(cfdir / "crudeoilm_prices.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts_utc": same_ts,
                "product": "CRUDEOILM",
                "prices": {"1000.0:CE": {"side": "CE", "token": "CE1", "ltp": ltp}},
            }) + "\n")
    rc = resolver.main(["--products", "CRUDEOILM"])
    assert rc == 0
    rows = [json.loads(l) for l in resolver._RESOLVED_PATH.read_text().splitlines()]
    # two rows tie on timestamp → resolver picks lexicographic outcome via if/elif
    assert rows[0]["outcome"] in ("SL_FIRST", "T1_FIRST")


def test_resolver_unresolved_no_prices(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    rc = resolver.main(["--products", "CRUDEOILM"])
    assert rc == 0
    rows = [json.loads(l) for l in resolver._RESOLVED_PATH.read_text().splitlines()]
    assert rows[0]["outcome"] == "UNRESOLVED"
    assert rows[0]["reason"] == "NO_POST_REJECTION_PRICES"


def test_resolver_ignores_non_threshold_only(isolated_dirs):
    cfdir, _ = isolated_dirs
    ts = datetime.now(timezone.utc).isoformat()
    with open(cfdir / "crudeoilm_counterfactual.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts_utc": ts, "product": "CRUDEOILM", "confidence": 62.0,
            "threshold_only": False, "hypothetical_contract": {"token": "CE1"},
        }) + "\n")
    rc = resolver.main(["--products", "CRUDEOILM"])
    assert rc == 0
    if resolver._RESOLVED_PATH.exists():
        rows = resolver._RESOLVED_PATH.read_text().strip().splitlines()
        assert not rows


def test_resolver_idempotent(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 10.0, cfdir)
    _price("CRUDEOILM", 58, "CE1", 11.5, cfdir)
    resolver.main(["--products", "CRUDEOILM"])
    n1 = len(resolver._RESOLVED_PATH.read_text().strip().splitlines())
    resolver.main(["--products", "CRUDEOILM"])
    n2 = len(resolver._RESOLVED_PATH.read_text().strip().splitlines())
    assert n1 == n2 == 1, "resolver must not duplicate resolved rows"


def test_resolver_mfe_mae_computed(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 10.0, cfdir)
    _price("CRUDEOILM", 58, "CE1", 11.5, cfdir)  # mfe +15%
    _price("CRUDEOILM", 57, "CE1", 9.5, cfdir)   # mae -5%
    resolver.main(["--products", "CRUDEOILM"])
    row = json.loads(resolver._RESOLVED_PATH.read_text().splitlines()[0])
    assert row["entry_price"] == 10.0
    assert abs(row["mfe_pct"] - 15.0) < 1e-6
    assert abs(row["mae_pct"] - (-5.0)) < 1e-6


def test_resolver_uses_product_thresholds_not_hardcoded(isolated_dirs):
    cfdir, _ = isolated_dirs
    _rej(cfdir, "CRUDEOILM", 62.0, 60, "CE1")
    _price("CRUDEOILM", 59, "CE1", 100.0, cfdir)
    _price("CRUDEOILM", 58, "CE1", 108.0, cfdir)  # +8% < T1 15%
    resolver.main(["--products", "CRUDEOILM"])
    row = json.loads(resolver._RESOLVED_PATH.read_text().splitlines()[0])
    assert row["outcome"] == "UNRESOLVED"
    # t1_price reflects product's 15%, not a hardcoded different value
    assert abs(row["t1_price"] - 115.0) < 1e-6
    assert abs(row["sl_price"] - 92.0) < 1e-6


def test_resolver_skips_unknown_product(isolated_dirs):
    rc = resolver.main(["--products", "BOGUS"])
    assert rc in (0, 2)
