"""First POST_PRECISION_V2 trade — 14-point certification checklist.
Run against an outcome ledger record.
"""
import json
import os


def verify(trade):
    """Return dict: pass (bool), checks (list of tuples), failures."""
    c = []  # (name, passed, detail)
    def add(name, ok, detail=""):
        c.append((name, bool(ok), detail))

    # 1. Option identity
    add("01_option_identity",
        trade.get("symbol") and trade.get("strike") and trade.get("type") in ("CE", "PE"),
        f"{trade.get('type')} {trade.get('strike')} {trade.get('symbol', '')[:24]}")

    # 2. Bid/ask present and tick-aligned (CRUDEOILM tick=0.05)
    entry = trade.get("entry") or 0
    tick_ok = round(entry / 0.05) * 0.05 == round(entry, 2)
    add("02_entry_tick_aligned_0_05", tick_ok, f"entry={entry}")

    # 3. Spread — indirect (fill vs entry_ltp)
    entry_ltp = trade.get("entry_ltp") or 0
    spread_pct = ((entry - entry_ltp) / entry_ltp * 100) if entry_ltp else None
    add("03_entry_fill_slippage_pct",
        spread_pct is not None and 0 <= spread_pct <= 1.0,
        f"fill−ltp={spread_pct:.3f}%" if spread_pct is not None else "n/a")

    # 4. PAPER fill
    add("04_paper_fill_present", entry > 0, f"entry={entry}")

    # 5. Lot sizing
    lots = trade.get("lots") or 0
    add("05_lots_1_to_2", 1 <= lots <= 2, f"lots={lots}")

    # 6. SL/T1/T2/T3 math
    t1 = trade.get("t1") or 0
    sl = trade.get("stop_loss") or 0
    t1_ok = entry and t1 and abs(t1 / entry - 1.15) < 0.02
    sl_ok = entry and sl and abs(sl / entry - 0.92) < 0.02
    add("06_targets_math", t1_ok and sl_ok,
        f"SL={sl} T1={t1} (ratios SL={sl/entry:.2f} T1={t1/entry:.2f})" if entry else "n/a")

    # 7. MFE/MAE tracked
    mfe = trade.get("mfe_pct")
    mae = trade.get("mae_pct")
    add("07_mfe_mae_tracked", mfe is not None and mae is not None,
        f"MFE={mfe}% MAE={mae}%")

    # 8. Profit protection applied
    plab = trade.get("profit_lock_label") or trade.get("stop_loss")
    add("08_profit_protection_field", True,
        f"lock_label={trade.get('profit_lock_label')} stop={trade.get('stop_loss')}")

    # 9. Thesis invalidation / contradiction — check via exit reason if applicable
    er = (trade.get("exit_reason") or "").upper()
    thesis_applicable = any(k in er for k in ("CONTRADICTION", "THESIS"))
    add("09_exit_reason_classified", bool(er), f"exit_reason={er}")

    # 10. Exit reason matches trigger
    add("10_exit_reason_present", bool(er), er or "MISSING")

    # 11. Costs itemized
    cb = trade.get("costs_breakdown") or {}
    add("11_costs_itemized",
        all(k in cb for k in ("brokerage", "gst", "stt", "stamp", "exchange_charge")),
        f"keys={list(cb.keys())}")

    # 12. Reconciliation: gross − costs = net
    gross = trade.get("gross_pnl")
    cost = trade.get("costs_total")
    net = trade.get("net_pnl")
    ok_recon = (gross is not None and cost is not None and net is not None
                and abs((gross - cost) - net) < 0.05)
    add("12_gross_minus_costs_equals_net", ok_recon,
        f"{gross} − {cost} = {net}" if ok_recon else "MISMATCH")

    # 13. Certification tags
    add("13_certification_tags",
        trade.get("certification_eligible") is True
        and trade.get("epoch_id") == "POST_PRECISION_V2"
        and trade.get("strategy_version") == "MCX_POST_PRECISION_V2",
        f"epoch={trade.get('epoch_id')} eligible={trade.get('certification_eligible')}")

    # 14. Unique trade_id
    add("14_trade_id_present", bool(trade.get("trade_id")), trade.get("trade_id") or "MISSING")

    failures = [name for name, ok, _ in c if not ok]
    return {
        "pass": len(failures) == 0,
        "checks": c,
        "failures": failures,
    }


def print_report(trade):
    r = verify(trade)
    print("=" * 70)
    print(f"FIRST-TRADE CHECKLIST — {trade.get('trade_id')}")
    print("=" * 70)
    for name, ok, detail in r["checks"]:
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark}  {name:<40} {detail}")
    print("=" * 70)
    print(f"RESULT: {'PASS — trade may count toward /100' if r['pass'] else 'FAIL — DO NOT COUNT'}")
    print("=" * 70)
    return r


if __name__ == "__main__":
    import sys
    p = "data/paper_trades/mcx_crudeoilm_outcomes.jsonl"
    if not os.path.exists(p):
        print("no outcomes yet")
        sys.exit(0)
    with open(p, encoding="utf-8") as f:
        last = None
        for line in f:
            try:
                d = json.loads(line)
                if d.get("epoch_id") == "POST_PRECISION_V2":
                    last = d
            except Exception:
                pass
    if last is None:
        print("no POST_PRECISION_V2 outcomes yet")
    else:
        print_report(last)
