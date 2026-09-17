"""Section 7.9-7.11 — real-depth VWAP fill. No synthetic path."""
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _tick_round(price, tick):
    if not tick or tick <= 0:
        return round(price, 6)
    return round(round(price / tick) * tick, 6)


def depth_vwap_for_buy(asks, requested_qty, tick=0.05):
    """Walk asks ascending. Return (fill_price, filled_qty, levels_consumed,
    worst_price, status).
    Insufficient depth → ('INSUFFICIENT_VISIBLE_DEPTH', 0, 0, None, ...).
    """
    if not asks:
        return None, 0, 0, None, "NO_ASK_DEPTH"
    if requested_qty <= 0:
        return None, 0, 0, None, "INVALID_QUANTITY"
    remaining = requested_qty
    notional = 0.0
    consumed = 0
    worst = None
    for lvl in asks:
        avail = lvl.get("quantity", 0)
        if avail <= 0:
            continue
        take = min(remaining, avail)
        notional += take * lvl["price"]
        remaining -= take
        consumed += 1
        worst = lvl["price"]
        if remaining <= 0:
            break
    if remaining > 0:
        return None, 0, 0, None, "INSUFFICIENT_VISIBLE_DEPTH"
    vwap = notional / requested_qty
    return _tick_round(vwap, tick), requested_qty, consumed, worst, "OK"


def depth_vwap_for_sell(bids, requested_qty, tick=0.05):
    """Walk bids descending. Symmetric to buy."""
    if not bids:
        return None, 0, 0, None, "NO_BID_DEPTH"
    if requested_qty <= 0:
        return None, 0, 0, None, "INVALID_QUANTITY"
    remaining = requested_qty
    notional = 0.0
    consumed = 0
    worst = None
    for lvl in bids:
        avail = lvl.get("quantity", 0)
        if avail <= 0:
            continue
        take = min(remaining, avail)
        notional += take * lvl["price"]
        remaining -= take
        consumed += 1
        worst = lvl["price"]
        if remaining <= 0:
            break
    if remaining > 0:
        return None, 0, 0, None, "INSUFFICIENT_VISIBLE_DEPTH"
    vwap = notional / requested_qty
    return _tick_round(vwap, tick), requested_qty, consumed, worst, "OK"


def compute_paper_fill_v2(quote, direction, requested_qty, tick=0.05):
    """Section 7.9 + 7.11 canonical fill using a validated ExecutionQuoteV1.
    Returns dict with fill details. NO synthetic fallback.
    """
    if not quote or quote.get("validation_status") != "VALID":
        return {"status": "QUOTE_INVALID",
                "rejection_reasons": (quote or {}).get("rejection_reasons", [])}
    if direction == "BUY":
        fill, filled, levels, worst, status = depth_vwap_for_buy(
            quote.get("asks"), requested_qty, tick)
    elif direction == "SELL":
        fill, filled, levels, worst, status = depth_vwap_for_sell(
            quote.get("bids"), requested_qty, tick)
    else:
        return {"status": "INVALID_DIRECTION"}
    if status != "OK":
        return {"status": status}
    return {
        "status": "OK",
        "fill_price": fill,
        "requested_quantity": requested_qty,
        "filled_quantity": filled,
        "levels_consumed": levels,
        "worst_level_price": worst,
        "fill_method": "DEPTH_VWAP",
        "source_quote_hash": quote.get("raw_payload_hash"),
        "source_mode": quote.get("source_mode"),
    }


if __name__ == "__main__":
    asks = [
        {"price": 10.00, "quantity": 40, "orders": 2},
        {"price": 10.05, "quantity": 40, "orders": 2},
        {"price": 10.10, "quantity": 20, "orders": 1},
    ]
    bids = [
        {"price": 9.95, "quantity": 30, "orders": 1},
        {"price": 9.90, "quantity": 50, "orders": 2},
        {"price": 9.85, "quantity": 40, "orders": 1},
    ]
    # Section 7.9 worked example
    print("buy 100:", depth_vwap_for_buy(asks, 100, tick=0.05))
    # Expected ~ (40*10 + 40*10.05 + 20*10.10)/100 = 10.035 → tick-rounded 10.05
    print("sell 80:", depth_vwap_for_sell(bids, 80, tick=0.05))
    print("buy 200 (insufficient):", depth_vwap_for_buy(asks, 200, tick=0.05))
