"""MCX learning layer — collects features per trade. Recommends only.
STRICT: does not modify strategy during certification epoch.
"""
import json
import os
from datetime import datetime

# Backward-compat default
LEARN_PATH = "data/paper_trades/mcx_crudeoilm_learning.jsonl"


def learn_path(product="CRUDEOILM"):
    return f"data/paper_trades/mcx_{product.lower()}_learning.jsonl"


def collect(trade, product="CRUDEOILM"):
    """Persist per-trade feature vector for offline analysis."""
    features = {
        "trade_id": trade.get("trade_id"),
        "epoch_id": trade.get("epoch_id"),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "entry_time": trade.get("entry_time"),
        "exit_time": trade.get("exit_time"),
        "exit_reason": trade.get("exit_reason"),
        "win_classification": trade.get("win_classification"),
        "setup": trade.get("setup"),
        "regime_at_entry": trade.get("regime_at_entry"),
        "structure_at_entry": trade.get("structure_at_entry"),
        "vwap_at_entry": trade.get("vwap_at_entry"),
        "long_conf_at_entry": trade.get("long_conf_at_entry"),
        "short_conf_at_entry": trade.get("short_conf_at_entry"),
        "tech_score_at_entry": trade.get("tech_score_at_entry"),
        "chain_score_at_entry": trade.get("chain_score_at_entry"),
        "external_score_at_entry": trade.get("external_score_at_entry"),
        "entry_quality_at_entry": trade.get("entry_quality_at_entry"),
        "greeks_at_entry": trade.get("greeks_at_entry"),
        "mfe_pct": trade.get("mfe_pct"),
        "mae_pct": trade.get("mae_pct"),
        "net_pnl": trade.get("net_pnl"),
        "gross_pnl": trade.get("gross_pnl"),
        "costs_total": trade.get("costs_total"),
    }
    p = learn_path(product)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(features, default=str) + "\n")
    return features


def recommend():
    """Placeholder — will return improvement proposals after 30+ trades.
    Never applied automatically. Only surfaced to operator for review.
    """
    if not os.path.exists(LEARN_PATH):
        return {"status": "NO_DATA", "note": "learning collection empty"}
    n = sum(1 for _ in open(LEARN_PATH, encoding="utf-8"))
    if n < 30:
        return {"status": "COLLECTING", "n": n, "need": 30}
    return {"status": "READY_FOR_REVIEW", "n": n,
            "note": "run offline analysis; propose V3 after walk-forward validation"}


if __name__ == "__main__":
    print(recommend())
