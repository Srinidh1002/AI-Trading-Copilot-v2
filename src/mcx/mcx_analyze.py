"""MCX Phase-I analytics — reads outcomes/predictions. Read-only.
"""
import json
import os
from collections import defaultdict


def _load(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def analyze():
    outcomes = _load(f"data/paper_trades/mcx_{'crudeoilm'}_outcomes.jsonl")
    v2 = [t for t in outcomes if t.get("epoch_id") == "POST_PRECISION_V2"]
    if not v2:
        return {"total_v2": 0, "note": "no POST_PRECISION_V2 outcomes yet"}

    wins = [t for t in v2 if t.get("win_classification") == "T1_WIN"]
    losses = [t for t in v2 if t.get("win_classification") == "SL_LOSS"]
    total_net = sum(t.get("net_pnl", 0) or 0 for t in v2)
    by_regime = defaultdict(lambda: {"w": 0, "l": 0})
    by_setup = defaultdict(lambda: {"w": 0, "l": 0})
    by_hour = defaultdict(lambda: {"w": 0, "l": 0})
    by_conf = defaultdict(lambda: {"w": 0, "l": 0})

    for t in v2:
        cls = "w" if t.get("win_classification") == "T1_WIN" else "l"
        reg = t.get("regime_at_entry") or "?"
        setup = t.get("setup") or "?"
        hh = (t.get("entry_time") or "")[11:13] or "?"
        lc = t.get("long_conf_at_entry")
        sc = t.get("short_conf_at_entry")
        conf = max(lc or 0, sc or 0)
        bucket = f"{int(conf // 10) * 10}-{int(conf // 10) * 10 + 9}"
        by_regime[reg][cls] += 1
        by_setup[setup][cls] += 1
        by_hour[hh][cls] += 1
        by_conf[bucket][cls] += 1

    return {
        "total_v2": len(v2),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(v2) * 100, 1) if v2 else 0,
        "certification_threshold_pct": 80.0,
        "total_net_pnl": round(total_net, 2),
        "by_regime": dict(by_regime),
        "by_setup": dict(by_setup),
        "by_hour": dict(by_hour),
        "by_confidence_bucket": dict(by_conf),
    }


if __name__ == "__main__":
    import json as j
    print(j.dumps(analyze(), indent=2))
