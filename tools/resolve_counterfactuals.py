"""Offline counterfactual resolver for MCX threshold-only rejections.

Reads:
  data/paper_trades/counterfactual/<product>_counterfactual.jsonl
      threshold-only rejections with a hypothetical contract
  data/paper_trades/counterfactual/<product>_prices.jsonl
      per-cycle CE/PE LTP evidence captured from the native chain

Writes (idempotent):
  data/paper_trades/counterfactual_resolved.jsonl

For each threshold-only rejection, look up subsequent prices for the
rejection's contract token, use the first observed LTP as the hypothetical
entry, compute SL/T1/T2/T3 from the product config, and walk forward to
determine whether SL or T1 was touched first.

Never infers option premium from futures prices. Never writes runtime
state. Never influences live decisions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

_TRADES = REPO_ROOT / "data" / "paper_trades"
_CF_DIR = _TRADES / "counterfactual"
_RESOLVED_PATH = _TRADES / "counterfactual_resolved.jsonl"

_SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
_RESOLVER_VERSION = 1


def _read_jsonl(path):
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _product_thresholds(product):
    try:
        from mcx.mcx_contracts import PRODUCTS
        cfg = PRODUCTS.get(product)
    except Exception:
        cfg = None
    if not cfg:
        return None
    return {
        "sl_pct": float(cfg["stop_loss_pct"]) / 100.0,
        "t1_pct": float(cfg["t1_pct"]) / 100.0,
        "t2_pct": float(cfg["t2_pct"]) / 100.0,
        "t3_pct": float(cfg["t3_pct"]) / 100.0,
    }


def _existing_keys():
    keys = set()
    if _RESOLVED_PATH.exists():
        for row in _read_jsonl(_RESOLVED_PATH):
            k = (row.get("rejection_ts_utc"), row.get("product"), row.get("token"))
            if k[0] and k[1] and k[2]:
                keys.add(k)
    return keys


def _price_observations_for_token(prices_rows, token, after_ts):
    obs = []
    for row in prices_rows:
        ts = _parse_ts(row.get("ts_utc"))
        if ts is None:
            continue
        if after_ts is not None and ts <= after_ts:
            continue
        prices = row.get("prices") or {}
        for _strike, entry in prices.items():
            if str(entry.get("token")) == str(token):
                ltp = entry.get("ltp")
                if isinstance(ltp, (int, float)) and ltp > 0:
                    obs.append((ts, float(ltp)))
    obs.sort(key=lambda p: p[0])
    return obs


def resolve_one(rejection, prices_rows, thresholds):
    token = (rejection.get("hypothetical_contract") or {}).get("token")
    if not token:
        return None
    rej_ts = _parse_ts(rejection.get("ts_utc"))
    if rej_ts is None:
        return None
    obs = _price_observations_for_token(prices_rows, token, rej_ts)
    if not obs:
        return {
            "outcome": "UNRESOLVED",
            "reason": "NO_POST_REJECTION_PRICES",
            "observations": 0,
        }
    entry_ts, entry_price = obs[0]
    sl = entry_price * (1.0 + thresholds["sl_pct"])
    t1 = entry_price * (1.0 + thresholds["t1_pct"])
    t2 = entry_price * (1.0 + thresholds["t2_pct"])
    t3 = entry_price * (1.0 + thresholds["t3_pct"])

    first_sl_ts = None
    first_t1_ts = None
    first_t2_ts = None
    first_t3_ts = None
    mfe = entry_price
    mae = entry_price
    for ts, ltp in obs:
        if ltp > mfe:
            mfe = ltp
        if ltp < mae:
            mae = ltp
        if first_sl_ts is None and ltp <= sl:
            first_sl_ts = ts
        if first_t1_ts is None and ltp >= t1:
            first_t1_ts = ts
        if first_t2_ts is None and ltp >= t2:
            first_t2_ts = ts
        if first_t3_ts is None and ltp >= t3:
            first_t3_ts = ts

    if first_sl_ts and first_t1_ts:
        outcome = "SL_FIRST" if first_sl_ts < first_t1_ts else "T1_FIRST"
    elif first_t1_ts:
        outcome = "T1_FIRST"
    elif first_sl_ts:
        outcome = "SL_FIRST"
    else:
        outcome = "UNRESOLVED"

    return {
        "outcome": outcome,
        "entry_ts_utc": entry_ts.isoformat(),
        "entry_price": entry_price,
        "sl_price": sl,
        "t1_price": t1,
        "t2_price": t2,
        "t3_price": t3,
        "mfe_pct": (mfe - entry_price) / entry_price * 100.0,
        "mae_pct": (mae - entry_price) / entry_price * 100.0,
        "first_t1_ts_utc": first_t1_ts.isoformat() if first_t1_ts else None,
        "first_sl_ts_utc": first_sl_ts.isoformat() if first_sl_ts else None,
        "first_t2_ts_utc": first_t2_ts.isoformat() if first_t2_ts else None,
        "first_t3_ts_utc": first_t3_ts.isoformat() if first_t3_ts else None,
        "observations": len(obs),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", default=",".join(_SUPPORTED))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    products = tuple(p.strip().upper() for p in args.products.split(",") if p.strip())
    existing = _existing_keys()
    resolved_rows = []
    stats = {"attempted": 0, "skipped_already": 0, "resolved": 0,
             "t1_first": 0, "sl_first": 0, "unresolved": 0}

    for product in products:
        cf_path = _CF_DIR / (product.lower() + "_counterfactual.jsonl")
        prices_path = _CF_DIR / (product.lower() + "_prices.jsonl")
        rejections = _read_jsonl(cf_path)
        prices = _read_jsonl(prices_path)
        thresholds = _product_thresholds(product)
        if thresholds is None:
            print("[" + product + "] thresholds unavailable; skipping")
            continue
        for rej in rejections:
            if not rej.get("threshold_only"):
                continue
            token = (rej.get("hypothetical_contract") or {}).get("token")
            key = (rej.get("ts_utc"), product, token)
            if key in existing:
                stats["skipped_already"] += 1
                continue
            stats["attempted"] += 1
            res = resolve_one(rej, prices, thresholds)
            if res is None:
                continue
            row = {
                "rejection_ts_utc": rej.get("ts_utc"),
                "product": product,
                "confidence": rej.get("confidence"),
                "direction": rej.get("direction"),
                "regime": rej.get("regime"),
                "option_side": rej.get("option_side"),
                "symbol": (rej.get("hypothetical_contract") or {}).get("symbol"),
                "token": token,
                "resolver_version": _RESOLVER_VERSION,
            }
            row.update(res)
            resolved_rows.append(row)
            if res.get("outcome") == "T1_FIRST":
                stats["t1_first"] += 1
            elif res.get("outcome") == "SL_FIRST":
                stats["sl_first"] += 1
            elif res.get("outcome") == "UNRESOLVED":
                stats["unresolved"] += 1

    print("attempted=" + str(stats["attempted"])
          + " skipped_already=" + str(stats["skipped_already"]))
    print("resolved=" + str(len(resolved_rows))
          + " t1_first=" + str(stats["t1_first"])
          + " sl_first=" + str(stats["sl_first"])
          + " unresolved=" + str(stats["unresolved"]))

    if args.dry_run:
        for r in resolved_rows[:10]:
            print("  " + r["product"] + " conf=" + str(r["confidence"])
                  + " outcome=" + r["outcome"]
                  + " mfe=" + str(r.get("mfe_pct"))
                  + " mae=" + str(r.get("mae_pct")))
        return 0

    if resolved_rows:
        _RESOLVED_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_RESOLVED_PATH, "a", encoding="utf-8") as f:
            for r in resolved_rows:
                f.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        print("WROTE " + str(len(resolved_rows)) + " rows -> " + str(_RESOLVED_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
