"""Expectancy by market and by confidence bucket from *_outcomes.jsonl."""
from __future__ import annotations
import json, os
from collections import defaultdict

_TRADES = os.path.join("data", "paper_trades")
_MARKETS = ("nifty", "sensex", "mcx_crudeoilm", "mcx_goldm", "mcx_natgasmini")


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


def main():
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
    print("-- expectancy by confidence bucket (pooled) --")
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


if __name__ == "__main__":
    main()
