"""MCX cost model — spec §24. Separate brokerage, exchange, statutory, taxes.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_contracts import PRODUCTS


def compute_costs(entry_premium, exit_premium, lots, product, side="BUY"):
    """Return itemized cost dict. Values calibrated against MCX published schedule;
    update before live certification."""
    spec = PRODUCTS.get(product.upper())
    if not spec:
        return {"status": "UNKNOWN_PRODUCT"}
    mult = spec["cash_multiplier"]
    # Turnover in rupees
    entry_turnover = entry_premium * mult * lots
    exit_turnover = exit_premium * mult * lots
    total_turnover = entry_turnover + exit_turnover

    # Brokerage (approx Angel One MCX: ₹20/order flat, 2 orders)
    brokerage = 20.0 * 2

    # Exchange transaction charge (MCX options ~₹0.05 per lakh on premium for non-agri)
    exchange_charge = total_turnover * 0.000005

    # SEBI turnover fee (~₹10 per crore = 1e-6)
    sebi_fee = total_turnover * 0.000001

    # GST 18% on (brokerage + exchange + sebi)
    gst = (brokerage + exchange_charge + sebi_fee) * 0.18

    # STT: options on futures — 0.05% on sell-side premium only (post-Oct 2024 rules;
    # verify before live). Applied to exit turnover for long options.
    stt = exit_turnover * 0.0005 if side == "BUY" else entry_turnover * 0.0005

    # Stamp duty 0.003% on buy side
    stamp = entry_turnover * 0.00003 if side == "BUY" else exit_turnover * 0.00003

    total = brokerage + exchange_charge + sebi_fee + gst + stt + stamp
    return {
        "status": "OK",
        "brokerage": round(brokerage, 2),
        "exchange_charge": round(exchange_charge, 2),
        "sebi_fee": round(sebi_fee, 2),
        "gst": round(gst, 2),
        "stt": round(stt, 2),
        "stamp": round(stamp, 2),
        "total": round(total, 2),
    }


def net_pnl(entry_premium, exit_premium, lots, product, side="BUY"):
    spec = PRODUCTS.get(product.upper())
    if not spec:
        return {"status": "UNKNOWN_PRODUCT"}
    mult = spec["cash_multiplier"]
    if side == "BUY":
        gross = (exit_premium - entry_premium) * mult * lots
    else:
        gross = (entry_premium - exit_premium) * mult * lots
    costs = compute_costs(entry_premium, exit_premium, lots, product, side)
    if costs.get("status") != "OK":
        return {"status": costs.get("status")}
    net = gross - costs["total"]
    cost_ratio = abs(costs["total"]) / abs(gross) if gross else 0
    return {
        "status": "OK",
        "gross_pnl": round(gross, 2),
        "costs_total": costs["total"],
        "costs_breakdown": costs,
        "net_pnl": round(net, 2),
        "cost_to_gross_ratio": round(cost_ratio, 4) if gross else None,
    }


if __name__ == "__main__":
    # Test: 2 lots, entry ₹332, exit ₹380 (winning trade)
    r = net_pnl(332.15, 380.0, 2, "CRUDEOILM", "BUY")
    print(r)
