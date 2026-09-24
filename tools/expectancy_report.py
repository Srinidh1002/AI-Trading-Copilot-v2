"""Expectancy by market and by confidence bucket.

Section 1 - real trades from *_outcomes.jsonl.
Section 2 - counterfactual threshold-only rejections from
            counterfactual_resolved.jsonl (research only).

Never recommends changing ENTRY_THRESHOLD; reports only.
"""
from __future__ import annotations
import json, os
from collections import defaultdict

_TRADES = os.path.join("data", "paper_trades")
_MARKETS = ("nifty", "sensex", "mcx_crudeoilm", "mcx_goldm", "mcx_natgasmini")
_RESOLVED = os.path.join(_TRADES, "counterfactual_resolved.jsonl")
_BANDS = ((40, 49), (50, 54), (55, 59), (60, 64), (65, 69))


def _jsonl(path):
    if not os.path.exists(path):
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
                pass
    return out


def _pnl(row):
    for k in ("pnl_pct", "return_pct", "pnl_percent", "realized_pnl_pct"):
        if row.get(k) is not None:
            return float(row[k])
    return None


def _conf(row):
    for k in ("entry_confidence", "confidence", "signal_confidence"):
        if row.get(k) is not None:
            return float(row[k])
    return None


def _bucket(c):
    if c is None:
        return "unknown"
    lo = int(c // 10) * 10
    return f"{lo}-{lo+9}"


def _summary(vals):
    if not vals:
        return None
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = sum(losses) / len(losses) if losses else 0.0
    exp = (len(wins) / len(vals)) * aw + (len(losses) / len(vals)) * al
    return len(vals), len(wins), aw, al, exp


def _band_for(c):
    if c is None:
        return None
    for lo, hi in _BANDS:
        if lo <= c <= hi:
            return f"{lo}-{hi}"
    return None


def section_trades():
    print(f"{'market':<16} {'n':>5} {'wins':>5} {'win%':>7} {'avg_win':>9} {'avg_loss':>9} {'expect':>9}")
    for m in _MARKETS:
        vals = [p for p in (_pnl(r) for r in _jsonl(os.path.join(_TRADES, f"{m}_outcomes.jsonl"))) if p is not None]
        s = _summary(vals)
        if not s:
            print(f"{m:<16} {0:>5}")
            continue
        n, w, aw, al, exp = s
        print(f"{m:<16} {n:>5} {w:>5} {w / n * 100:>6.1f}% {aw:>9.2f} {al:>9.2f} {exp:>9.3f}")

    print()
    print("-- expectancy by confidence bucket (pooled real trades) --")
    buckets = defaultdict(list)
    for m in _MARKETS:
        for r in _jsonl(os.path.join(_TRADES, f"{m}_outcomes.jsonl")):
            p = _pnl(r)
            c = _conf(r)
            if p is None:
                continue
            buckets[_bucket(c)].append(p)
    for b in sorted(buckets):
        s = _summary(buckets[b])
        if s:
            n, w, _, _, exp = s
            print(f"  {b:<8} n={n:>4}  win%={w / n * 100:>5.1f}  expect={exp:>8.3f}")


def section_counterfactuals():
    rows = _jsonl(_RESOLVED)
    if not rows:
        print()
        print("-- counterfactual threshold-only rejections (no rows yet) --")
        return
    by_band = defaultdict(lambda: {"n": 0, "t1": 0, "sl": 0, "unres": 0,
                                    "mfe": [], "mae": []})
    for r in rows:
        c = r.get("confidence")
        band = _band_for(c)
        if band is None:
            continue
        b = by_band[band]
        b["n"] += 1
        outcome = r.get("outcome")
        if outcome == "T1_FIRST":
            b["t1"] += 1
        elif outcome == "SL_FIRST":
            b["sl"] += 1
        elif outcome == "UNRESOLVED":
            b["unres"] += 1
        if isinstance(r.get("mfe_pct"), (int, float)):
            b["mfe"].append(float(r["mfe_pct"]))
        if isinstance(r.get("mae_pct"), (int, float)):
            b["mae"].append(float(r["mae_pct"]))
    print()
    print("-- counterfactual threshold-only rejections by confidence band --")
    print(f"{'band':<8} {'n':>5} {'t1_first':>9} {'sl_first':>9} {'unres':>7} "
          f"{'t1_rate':>8} {'avg_mfe':>8} {'avg_mae':>8}")
    for band in [f"{lo}-{hi}" for lo, hi in _BANDS]:
        b = by_band.get(band)
        if not b or b["n"] == 0:
            continue
        denom = b["t1"] + b["sl"]
        rate = (b["t1"] / denom * 100.0) if denom else 0.0
        mfe = sum(b["mfe"]) / len(b["mfe"]) if b["mfe"] else 0.0
        mae = sum(b["mae"]) / len(b["mae"]) if b["mae"] else 0.0
        print(f"{band:<8} {b['n']:>5} {b['t1']:>9} {b['sl']:>9} {b['unres']:>7} "
              f"{rate:>7.1f}% {mfe:>8.2f} {mae:>8.2f}")


def main():
    section_trades()
    section_counterfactuals()
    print()
    print("NOTE: ENTRY_THRESHOLD remains 70. This report is read-only "
          "research and does not recommend changing it.")


if __name__ == "__main__":
    main()
