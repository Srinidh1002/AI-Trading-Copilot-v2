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
    from mcx.mcx_version import (
        get_product_epochs as _get_product_epochs,
        is_certification_eligible as _is_cert_eligible,
    )
    from mcx.mcx_version import get_product_epochs
    from mcx.mcx_certification import classify_win as _classify_win

    required = ["trade_id", "entry", "exit", "lots"]
    for k in required:
        if pos.get(k) is None:
            return {"status": "INCOMPLETE", "missing": k}

    net = compute_net(pos["entry"], pos["exit"], pos["lots"], product, side="BUY")
    if net.get("status") != "OK":
        return {"status": "COST_ERROR"}

    # Product registry is the sole epoch/version authority.
    product_cfg = (
        _get_product_epochs(product)
        or {}
    )

    # Preserve original campaign provenance; never relabel an old position.
    cfg = get_product_epochs(product) or {}
    epoch = pos.get("epoch_id") or pos.get("certification_epoch") or cfg.get("epoch")
    version = pos.get("strategy_version") or cfg.get("strategy_version")
    identity_ok = bool(cfg and (pos.get("epoch_id") or pos.get("certification_epoch"))
                       and pos.get("strategy_version")
                       and epoch == cfg.get("epoch")
                       and version == cfg.get("strategy_version"))
    # Certification gate: unique, closed, reconciled, non-synthetic
    registry_ok = _is_cert_eligible(product) and identity_ok
    cert_eligible = (
        registry_ok
        and pos.get("_synthetic") is not True
        and pos.get("exit") is not None
        and pos.get("entry") is not None
        and net["net_pnl"] is not None
    )

    result = dict(pos)
    result.update({
        "epoch_id": epoch,
        "strategy_version": version,
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



def accepted_ledger_gaps(state, product="CRUDEOILM"):
    """Return missing or contradictory accepted trade IDs; never modify history."""
    cfg = __import__("mcx.mcx_version", fromlist=["get_product_epochs"]).get_product_epochs(product) or {}
    accepted = {
        t["trade_id"]: t for t in state.get("completed_trades", [])
        if t.get("certification_accepted") is True
        and t.get("trade_id") in set(state.get("_counted_trade_ids", []))
        and t.get("epoch_id") == cfg.get("epoch")
        and t.get("strategy_version") == cfg.get("strategy_version")
    }
    if not accepted:
        return []
    ledger = outcomes_path(product)
    if not os.path.isfile(ledger):
        return sorted(accepted)
    matched = set()
    invalid = set()
    with open(ledger, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                return sorted(accepted)
            tid = row.get("trade_id")
            if tid not in accepted:
                continue
            if tid in matched or row.get("certification_accepted") is not True or (
                row.get("epoch_id"), row.get("strategy_version")
            ) != (cfg.get("epoch"), cfg.get("strategy_version")):
                invalid.add(tid)
            matched.add(tid)
    return sorted((set(accepted) - matched) | invalid)

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
            if (r.get('certification_accepted') is True
                and r.get("strategy_version") == target_version
                and r.get("epoch_id") == target_epoch):
                n += 1
    return n


if __name__ == "__main__":
    print("mcx_reconcile module loaded OK")
    print(f"Current certified count: {count_certified()}")
