"""Section 7.2 + 7.4 — extract real depth from Angel FULL response.
Handles both 'depth.buy/sell' and top-level 'bestFiveBuyData/SellData'.
"""
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_contracts import ANGEL_MASTER_SCALE


def _parse_level(raw):
    if not isinstance(raw, dict):
        return None
    try:
        p = float(raw.get("price", 0) or 0)
        q = int(raw.get("quantity", 0) or 0)
        o = int(raw.get("orders", 0) or 0)
    except Exception:
        return None
    if p <= 0:
        return None
    return {"price": round(p, 4), "quantity": q, "orders": o}


def extract_depth(full_row):
    """Return (bids, asks, depth_present, notes).
    Accepts variants:
      - {"depth": {"buy": [...], "sell": [...]}}
      - {"bestFiveBuyData": [...], "bestFiveSellData": [...]}
    """
    notes = []
    bids = []
    asks = []

    depth = full_row.get("depth") if isinstance(full_row, dict) else None
    if isinstance(depth, dict):
        for lvl in depth.get("buy") or []:
            r = _parse_level(lvl)
            if r: bids.append(r)
        for lvl in depth.get("sell") or []:
            r = _parse_level(lvl)
            if r: asks.append(r)

    if not bids:
        for lvl in (full_row.get("bestFiveBuyData") or []):
            r = _parse_level(lvl)
            if r: bids.append(r)
    if not asks:
        for lvl in (full_row.get("bestFiveSellData") or []):
            r = _parse_level(lvl)
            if r: asks.append(r)

    depth_present = bool(bids or asks)
    if not depth_present:
        notes.append("NO_DEPTH_FIELDS_PRESENT")

    # Validate ordering
    if bids != sorted(bids, key=lambda x: x["price"], reverse=True):
        notes.append("BIDS_WERE_UNSORTED")
        bids = sorted(bids, key=lambda x: x["price"], reverse=True)
    if asks != sorted(asks, key=lambda x: x["price"]):
        notes.append("ASKS_WERE_UNSORTED")
        asks = sorted(asks, key=lambda x: x["price"])

    return bids, asks, depth_present, notes


if __name__ == "__main__":
    # Simulate both schema variants
    row_a = {"depth": {"buy": [{"price": 99.9, "quantity": 100, "orders": 3}],
                       "sell": [{"price": 100.1, "quantity": 80, "orders": 2}]}}
    print("variant A:", extract_depth(row_a))
    row_b = {"bestFiveBuyData": [{"price": 99.9, "quantity": 100}],
             "bestFiveSellData": [{"price": 100.1, "quantity": 80}]}
    print("variant B:", extract_depth(row_b))
    row_c = {"ltp": 100}
    print("no depth:", extract_depth(row_c))
