"""MCX reconciliation — spec §23, §24, §27, §37.
Takes a closed trade, computes net P&L, validates uniqueness, marks certification.
"""
import json
import os
from datetime import datetime

# Backward-compat default (kept for any legacy call)
OUTCOMES_PATH = "data/paper_trades/mcx_crudeoilm_outcomes.jsonl"


def outcomes_path(product="CRUDEOILM"):
    """Return product-scoped outcomes ledger path."""
    return f"data/paper_trades/mcx_{product.lower()}_outcomes.jsonl"


def reconcile(pos, product="CRUDEOILM"):
    """pos must contain: trade_id, entry, exit, lots, entry_time, exit_time,
    exit_reason, max_profit_pct, min_profit_pct, type, strike.
    Returns dict with gross/net P&L + terminal status.
    """
    from mcx.mcx_costs import net_pnl as compute_net
    from mcx.mcx_version import is_certification_eligible as _is_cert_eligible
    from mcx.mcx_certification import classify_win as _classify_win

    required = ["trade_id", "entry", "exit", "lots"]
    for k in required:
        if pos.get(k) is None:
            return {"status": "INCOMPLETE", "missing": k}

    net = compute_net(pos["entry"], pos["exit"], pos["lots"], product, side="BUY")
    if net.get("status") != "OK":
        return {"status": "COST_ERROR"}

    # Certification gate: unique, closed, reconciled, non-synthetic
    registry_ok = _is_cert_eligible(product)
    cert_eligible = (
        registry_ok
        and pos.get("_synthetic") is not True
        and pos.get("exit") is not None
        and pos.get("entry") is not None
        and net["net_pnl"] is not None
    )

    result = dict(pos)
    result.update({
        "epoch_id": "POST_PRECISION_V2",
        "strategy_version": "MCX_POST_PRECISION_V2",
        "certification_eligible": cert_eligible,
        "registry_certification_eligible": registry_ok,
        "gross_pnl": net["gross_pnl"],
        "costs_total": net["costs_total"],
        "costs_breakdown": net["costs_breakdown"],
        "net_pnl": net["net_pnl"],
        "is_win": net["net_pnl"] > 0,
        "reconciled_at": datetime.now().isoformat(timespec="seconds"),
        "terminal_state": "RECONCILED",
    })
    result["win_classification"] = _classify_win(result)

    # Note on give-back
    peak = pos.get("max_profit_pct", 0) or 0
    if peak > 0 and "last_pnl_pct" in pos:
        result["profit_giveback_pct"] = round(peak - pos["last_pnl_pct"], 2)
    else:
        result["profit_giveback_pct"] = None

    return result


def is_duplicate(trade_id, product="CRUDEOILM"):
    """Check outcome ledger for duplicate trade_id (certification integrity)."""
    p = outcomes_path(product)
    if not os.path.exists(p):
        return False
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("trade_id") == trade_id:
                return True
    return False


def append_outcome(reconciled, product="CRUDEOILM"):
    p = outcomes_path(product)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if is_duplicate(reconciled.get("trade_id"), product=product):
        return {"status": "DUPLICATE_REJECTED", "trade_id": reconciled.get("trade_id")}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(reconciled, default=str) + "\n")
    return {"status": "APPENDED", "trade_id": reconciled.get("trade_id"),
            "certification_eligible": reconciled.get("certification_eligible")}


def count_certified(product="CRUDEOILM"):
    """Return count of certification-eligible trades for the product."""
    from mcx.mcx_version import get_product_epochs
    cfg = get_product_epochs(product) or {}
    target_epoch = cfg.get("epoch")
    target_version = cfg.get("strategy_version")
    p = outcomes_path(product)
    if not os.path.exists(p):
        return 0
    n = 0
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get("certification_eligible")
                and r.get("strategy_version") == target_version
                and r.get("epoch_id") == target_epoch):
                n += 1
    return n


if __name__ == "__main__":
    print("mcx_reconcile module loaded OK")
    print(f"Current POST_PRECISION_V2 certified count: {count_certified()}")
