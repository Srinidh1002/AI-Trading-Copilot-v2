"""Append-only, process-safe counterfactual capture for MCX rejections.

Every row is a THRESHOLD_ONLY candidate: the strategy passed every hard
gate (data quality, calendar, event risk, PCR, setup, expiry risk,
market evidence) and was rejected solely because the confidence did not
reach ENTRY_THRESHOLD.

Because three MCX worker processes run concurrently, this module writes
one file per product:
    data/paper_trades/counterfactual/<product>_counterfactual.jsonl

Only the worker for that product writes to its file, so no cross-process
locking is needed. Writes are line-buffered appends.

Never influences runtime decisions. Never takes additional provider calls.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


_LOG_DIR = os.path.join("data", "paper_trades", "counterfactual")


def _log_path(product):
    return os.path.join(_LOG_DIR, f"{str(product).lower()}_counterfactual.jsonl")


def _safe_contract(contract):
    """Reduce a strike-selection dict to non-sensitive identity fields."""
    if not isinstance(contract, dict):
        return None
    return {
        "symbol": contract.get("symbol"),
        "token": str(contract.get("token")) if contract.get("token") is not None else None,
        "strike": contract.get("strike"),
        "type": contract.get("type"),
        "ltp": contract.get("ltp"),
        "score": contract.get("score"),
    }


def log_rejection(
    *,
    product,
    confidence,
    direction,
    regime,
    blocking_reasons,
    threshold_only,
    signal_price=None,
    setup_id=None,
    underlying_future_symbol=None,
    future_price=None,
    expiry=None,
    dte=None,
    option_side=None,
    hypothetical_contract=None,
    attempt=None,
):
    """Append one rejection row. Process-safe by per-product file."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "product": product,
        "confidence": float(confidence),
        "direction": direction,
        "regime": regime,
        "blocking_reasons": list(blocking_reasons or []),
        "threshold_only": bool(threshold_only),
        "signal_price": signal_price,
        "setup_id": setup_id,
        "underlying_future_symbol": underlying_future_symbol,
        "future_price": future_price,
        "expiry": expiry,
        "dte": dte,
        "option_side": option_side,
        "hypothetical_contract": _safe_contract(hypothetical_contract),
        "attempt": attempt,
        "resolved": False,
    }
    with open(_log_path(product), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass

def log_cycle_prices(product, chain, *, attempt=None, price_window_steps=3):
    """Append per-cycle ATM CE/PE LTP evidence for the resolver.

    Pure slice of an already-fetched native chain. No provider calls.
    Records every in-window CE and PE strike's current LTP so an
    offline resolver can walk forward from a past rejection.
    """
    if not isinstance(chain, dict) or chain.get('status') != 'OK':
        return
    atm = chain.get('atm')
    if atm is None:
        return
    try:
        from mcx.mcx_contracts import PRODUCTS as _PRODUCTS
        step = (_PRODUCTS.get(product) or {}).get('strike_interval')
    except Exception:
        step = None
    if not step:
        return
    low = atm - price_window_steps * step
    high = atm + price_window_steps * step
    ts = datetime.now(timezone.utc).isoformat()
    ce = chain.get('ce_data') or {}
    pe = chain.get('pe_data') or {}
    prices = {}
    for strike, entry in ce.items():
        try:
            if low <= float(strike) <= high:
                prices[str(strike) + ':CE'] = {
                    'side': 'CE',
                    'token': str(entry.get('token')),
                    'symbol': entry.get('symbol'),
                    'ltp': entry.get('ltp'),
                    'bid': entry.get('bid'),
                    'ask': entry.get('ask'),
                    'oi': entry.get('oi'),
                }
        except Exception:
            continue
    for strike, entry in pe.items():
        try:
            if low <= float(strike) <= high:
                prices[str(strike) + ':PE'] = {
                    'side': 'PE',
                    'token': str(entry.get('token')),
                    'symbol': entry.get('symbol'),
                    'ltp': entry.get('ltp'),
                    'bid': entry.get('bid'),
                    'ask': entry.get('ask'),
                    'oi': entry.get('oi'),
                }
        except Exception:
            continue
    if not prices:
        return
    row = {
        'ts_utc': ts,
        'product': product,
        'attempt': attempt,
        'future_ltp': chain.get('future_ltp'),
        'atm': atm,
        'expiry': chain.get('expiry'),
        'prices': prices,
    }
    os.makedirs(_LOG_DIR, exist_ok=True)
    path = os.path.join(_LOG_DIR, str(product).lower() + '_prices.jsonl')
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, separators=(',', ':')) + '\n')
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
