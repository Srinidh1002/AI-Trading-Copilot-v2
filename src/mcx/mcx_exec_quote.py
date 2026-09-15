"""Section 7.5 — Canonical ExecutionQuoteV1. Immutable snapshot of real depth."""
import hashlib
import json
from datetime import datetime, timezone

# Section 7.7 default (uncalibrated — will be replaced by Monday live smoke)
EXECUTION_QUOTE_MAX_AGE_SECONDS = 20.0  # S7_STAGE_6_CALIBRATION — max of per-product (see exec_config.json)
EXECUTION_FRESHNESS_CALIBRATED = True  # S7_STAGE_6_CALIBRATION
EXECUTION_FRESHNESS_SOURCE = "S7_STAGE_6_CALIBRATION_2026-09-15"  # S7_STAGE_6_CALIBRATION

QUOTE_SOURCES = ("WS_DEPTH", "REST_FULL")

VALIDATION_STATUSES = ("VALID", "INVALID")

REJECTIONS = (
    "SYMBOL_TOKEN_MISMATCH", "WRONG_EXCHANGE", "NO_BID", "NO_ASK",
    "NEGATIVE_QUANTITY", "ZERO_BEST_BID", "ZERO_BEST_ASK",
    "CROSSED_BOOK_INVALID", "BIDS_NOT_SORTED", "ASKS_NOT_SORTED",
    "TICK_MISALIGNED", "NAN_VALUE", "STALE_QUOTE",
    "MISSING_FEED_TIME", "MISSING_PROVIDER_TIME",
)


def _hash(payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, sort_keys=True, default=str)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_nan(x):
    try:
        return x != x
    except Exception:
        return True


def make_execution_quote(
    product, option_symbol, token, exchange,
    option_type, strike, expiry,
    ltp, bids, asks,
    volume=None, open_interest=None,
    exchange_feed_time=None, exchange_trade_time=None,
    provider_received_at=None,
    provider="AngelOne", source_mode="REST_FULL",
    sequence_number=None, tick_size=None,
    raw_payload=None,
):
    """bids/asks must be lists of dicts: {price, quantity, orders}."""
    if provider_received_at is None:
        provider_received_at = datetime.now(timezone.utc).isoformat()
    bids = list(bids or [])
    asks = list(asks or [])
    best_bid = bids[0].get("price") if bids else None
    best_ask = asks[0].get("price") if asks else None
    spread = None
    spread_ticks = None
    midpoint = None
    if best_bid is not None and best_ask is not None:
        spread = round(best_ask - best_bid, 6)
        if tick_size and tick_size > 0:
            spread_ticks = round(spread / tick_size, 4)
        midpoint = round((best_bid + best_ask) / 2.0, 6)

    return {
        "product": product,
        "option_symbol": option_symbol,
        "token": str(token),
        "exchange": exchange,
        "option_type": option_type,
        "strike": strike,
        "expiry": expiry,
        "ltp": ltp,
        "bids": bids,
        "asks": asks,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_ticks": spread_ticks,
        "midpoint": midpoint,
        "volume": volume,
        "open_interest": open_interest,
        "exchange_feed_time": exchange_feed_time,
        "exchange_trade_time": exchange_trade_time,
        "provider_received_at": provider_received_at,
        "provider": provider,
        "source_mode": source_mode,
        "sequence_number": sequence_number,
        "raw_payload_hash": _hash(raw_payload) if raw_payload is not None else None,
        "tick_size": tick_size,
        "validation_status": "PENDING",
        "rejection_reasons": [],
    }


def validate_quote(q, expected_token, expected_exchange="MCX",
                   now_iso=None, max_age_seconds=None):
    """Section 7.6 + 7.7 validation. Pure function; returns (ok, quote_with_reasons)."""
    reasons = []
    q = dict(q)
    # identity
    if str(q.get("token")) != str(expected_token):
        reasons.append("SYMBOL_TOKEN_MISMATCH")
    if q.get("exchange") != expected_exchange:
        reasons.append("WRONG_EXCHANGE")
    # price presence
    bids = q.get("bids") or []
    asks = q.get("asks") or []
    if not bids:
        reasons.append("NO_BID")
    if not asks:
        reasons.append("NO_ASK")
    if bids and asks:
        bb = bids[0].get("price")
        ba = asks[0].get("price")
        if bb is None or _is_nan(bb) or bb <= 0:
            reasons.append("ZERO_BEST_BID")
        if ba is None or _is_nan(ba) or ba <= 0:
            reasons.append("ZERO_BEST_ASK")
        if bb is not None and ba is not None and bb > ba:
            reasons.append("CROSSED_BOOK_INVALID")
        # sorting
        bid_prices = [b.get("price") for b in bids if b.get("price") is not None]
        ask_prices = [a.get("price") for a in asks if a.get("price") is not None]
        if bid_prices != sorted(bid_prices, reverse=True):
            reasons.append("BIDS_NOT_SORTED")
        if ask_prices != sorted(ask_prices):
            reasons.append("ASKS_NOT_SORTED")
    # quantities
    for lvl in bids + asks:
        qty = lvl.get("quantity")
        if qty is None or _is_nan(qty) or qty < 0:
            reasons.append("NEGATIVE_QUANTITY")
            break
    # tick alignment
    ts = q.get("tick_size")
    if ts and ts > 0:
        for lvl in bids + asks:
            p = lvl.get("price")
            if p is None:
                continue
            if round(p / ts) * ts != round(p, 6):
                # loose check — allow 1e-6 fuzz
                if abs(round(p / ts) * ts - p) > 1e-6:
                    reasons.append("TICK_MISALIGNED")
                    break
    # timestamps
    if not q.get("exchange_feed_time"):
        reasons.append("MISSING_FEED_TIME")
    if not q.get("provider_received_at"):
        reasons.append("MISSING_PROVIDER_TIME")
    # freshness
    ref_now = now_iso or datetime.now(timezone.utc).isoformat()
    # S7_STAGE_6_CALIBRATION — resolution order:
    #   1. explicit max_age_seconds arg (tests)
    #   2. per-product config (exec_config.json)
    #   3. module-level global (fallback)
    #   4. UNCALIBRATED rejection
    _resolved_max_age = max_age_seconds
    if _resolved_max_age is None:
        _product = q.get("product")
        try:
            from mcx.mcx_exec_config import get_execution_quote_max_age_seconds as _cfg_age
            _resolved_max_age = _cfg_age(_product)
        except Exception:
            _resolved_max_age = None
        if _resolved_max_age is None and EXECUTION_FRESHNESS_CALIBRATED:
            _resolved_max_age = EXECUTION_QUOTE_MAX_AGE_SECONDS
    if _resolved_max_age is None:
        reasons.append("EXECUTION_FRESHNESS_UNCALIBRATED")
        q["execution_freshness_status"] = "UNCALIBRATED"
    else:
        max_age = _resolved_max_age
        try:
            recv = datetime.fromisoformat(q.get("provider_received_at"))
            now = datetime.fromisoformat(ref_now)
            if recv.tzinfo is None:
                recv = recv.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            age = (now - recv).total_seconds()
            if age > max_age:
                reasons.append("STALE_QUOTE")
            q["_age_seconds"] = round(age, 3)
            q["execution_freshness_status"] = "CALIBRATED"
        except Exception:
            reasons.append("MISSING_PROVIDER_TIME")

    q["validation_status"] = "INVALID" if reasons else "VALID"
    q["rejection_reasons"] = reasons
    return (len(reasons) == 0, q)


if __name__ == "__main__":
    q = make_execution_quote(
        product="CRUDEOILM", option_symbol="TEST", token="999",
        exchange="MCX", option_type="CE", strike=9500, expiry="2026-09-17",
        ltp=100.0, bids=[{"price": 99.9, "quantity": 100, "orders": 5}],
        asks=[{"price": 100.1, "quantity": 100, "orders": 5}],
        exchange_feed_time="2026-09-12T10:00:00+00:00", tick_size=0.05,
    )
    ok, q = validate_quote(q, "999")
    print("valid:", ok, "reasons:", q["rejection_reasons"])
