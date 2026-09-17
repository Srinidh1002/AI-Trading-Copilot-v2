"""MCX paper fill + lot sizing + P&L. Mirrors capital_engine.py for MCX.
Cash multiplier from contract spec (CRUDEOILM=10, GOLDM=10, NATGASMINI=250).
"""
from mcx.mcx_contracts import PRODUCTS


# Assumptions (per blueprint §19.1 fill model)
SLIPPAGE_PCT = 0.001         # 0.1% conservative slippage when bid/ask unavailable
SPREAD_FALLBACK_PCT = 0.001  # ±0.1% synthetic spread when depth unavailable


def synth_bid_ask(ltp):
    """MCX getMarketData doesn't return depth — synth conservative bid/ask."""
    if ltp <= 0:
        return 0, 0
    return round(ltp * (1 - SPREAD_FALLBACK_PCT), 2), round(ltp * (1 + SPREAD_FALLBACK_PCT), 2)


def compute_paper_fill(bid, ask, ltp, direction="BUY"):
    """Return (fill_price, status). Buy near ask + slippage, sell near bid - slippage."""
    if not ltp or ltp <= 0:
        return None, "BAD_LTP"
    # Use actual bid/ask if present, else synth
    if not bid or not ask or bid <= 0 or ask <= 0:
        bid, ask = synth_bid_ask(ltp)

    if direction == "BUY":
        base = ask if ask > 0 else ltp
        fill = base * (1 + SLIPPAGE_PCT)
    else:
        base = bid if bid > 0 else ltp
        fill = base * (1 - SLIPPAGE_PCT)

    return round(fill, 2), "OK"


def compute_lots(premium, product, deployable_capital=100_000, risk_fraction=0.10):
    """1 lot cash = premium * cash_multiplier. Risk budget = capital * risk_fraction."""
    spec = PRODUCTS.get(product.upper())
    if not spec or premium <= 0:
        return 0, 0, 0
    mult = spec["cash_multiplier"]
    one_lot_cash = premium * mult
    risk_budget = deployable_capital * risk_fraction
    # Conservative: max 1 lot per trade to keep MCX PAPER safe (per-trade risk small)
    max_lots_by_cash = int(deployable_capital / one_lot_cash) if one_lot_cash > 0 else 0
    max_lots = min(max_lots_by_cash, 2)   # hard cap 2 lots for now
    return max_lots, one_lot_cash, risk_budget


def compute_costs(entry, exit_, lots, product):
    """Modeled costs: brokerage + STT + slippage already in fill."""
    spec = PRODUCTS.get(product.upper())
    if not spec:
        return 0.0
    mult = spec["cash_multiplier"]
    notional_entry = entry * mult * lots
    notional_exit = exit_ * mult * lots
    # Rough: ₹20/lot brokerage each side + 0.05% STT on sell + 0.005% exchange charge
    brokerage = 20 * lots * 2
    stt = notional_exit * 0.0005
    exch = (notional_entry + notional_exit) * 0.00005
    return round(brokerage + stt + exch, 2)


def compute_net_pnl(entry, exit_, lots, product, direction="BUY"):
    spec = PRODUCTS.get(product.upper())
    if not spec:
        return {}
    mult = spec["cash_multiplier"]
    if direction == "BUY":
        gross = (exit_ - entry) * mult * lots
    else:
        gross = (entry - exit_) * mult * lots
    costs = compute_costs(entry, exit_, lots, product)
    net = gross - costs
    net_pct = (net / (entry * mult * lots)) * 100 if entry > 0 and lots > 0 else 0
    return {
        "gross_pnl": round(gross, 2),
        "costs_total": round(costs, 2),
        "net_pnl": round(net, 2),
        "net_pnl_pct": round(net_pct, 2),
    }
