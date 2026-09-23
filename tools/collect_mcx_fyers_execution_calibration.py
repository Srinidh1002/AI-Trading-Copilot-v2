"""Read-only MCX FYERS execution calibration collector.

No orders. No state mutation. Only provider data reads. Requires a valid
FYERS access token in the canonical .env file. The operator runs this
manually on a provider-alive day; it is NOT automated.

Each collection session appends rows to:
  data/execution_evidence/mcx/fyers/<product>_<utc_iso>_<session_id>.jsonl

One row per observed contract depth sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

_EVIDENCE_DIR = REPO_ROOT / "data" / "execution_evidence" / "mcx" / "fyers"
_SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
_PROVIDER = "FYERS"


def _utc_iso():
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _extract_depth(row: dict):
    """Pull bids and asks from a FYERS FULL response row.

    FYERS standard normalizer surfaces `depth` as {bids: [...], asks: [...]}
    where each level is {price, volume, orders?}. We accept either key name.
    Returns (bids, asks) as lists of dicts.
    """
    depth = (row.get("depth") or {})
    bids = depth.get("bids") or depth.get("bid") or []
    asks = depth.get("asks") or depth.get("ask") or []
    if not isinstance(bids, list):
        bids = []
    if not isinstance(asks, list):
        asks = []
    return bids, asks


def _provider_ts(row: dict):
    for k in ("exchange_timestamp", "timestamp", "exchFeedTime", "exchTradeTime"):
        v = row.get(k)
        if v:
            return v
    return None


def _age_seconds(provider_ts, local_dt):
    if not provider_ts:
        return None
    try:
        pt = datetime.fromisoformat(str(provider_ts).replace("Z", "+00:00"))
    except Exception:
        return None
    if pt.tzinfo is None:
        pt = pt.replace(tzinfo=timezone.utc)
    return max(0.0, (local_dt - pt.astimezone(timezone.utc)).total_seconds())


def _select_atm(chain, future_ltp):
    """Pick the CE and PE contract nearest to future_ltp on the nearest expiry."""
    calls = chain.get("calls") or {}
    puts = chain.get("puts") or {}
    if not calls or not puts:
        return None
    all_strikes = sorted(set(list(calls.keys()) + list(puts.keys())))
    if not all_strikes:
        return None
    try:
        atm = min(all_strikes, key=lambda s: abs(float(s) - float(future_ltp)))
    except Exception:
        atm = all_strikes[len(all_strikes) // 2]
    ce = calls.get(atm)
    pe = puts.get(atm)
    return atm, ce, pe


def _emit_row(session_id, product, phase, contract, side, future_info, row, local_dt, ordinal):
    bids, asks = _extract_depth(row)
    provider_ts = _provider_ts(row)
    age = _age_seconds(provider_ts, local_dt)

    row_identity = {
        "product": product,
        "symbol": contract.get("symbol"),
        "token": contract.get("token"),
        "expiry": contract.get("expiry"),
        "strike": contract.get("strike"),
        "side": side,
        "bids": bids,
        "asks": asks,
        "provider_ts": provider_ts,
    }
    payload_hash = _hash_payload(row_identity)

    trading_unit = None
    try:
        from mcx.mcx_contracts import PRODUCTS as _PRODUCTS
        trading_unit = (_PRODUCTS.get(product) or {}).get("trading_unit")
    except Exception:
        trading_unit = None

    return {
        "session_id": session_id,
        "phase": phase,
        "provider": _PROVIDER,
        "product": product,
        "symbol": contract.get("symbol"),
        "token": contract.get("token"),
        "expiry": contract.get("expiry"),
        "strike": contract.get("strike"),
        "side": side,
        "future_symbol": (future_info or {}).get("symbol"),
        "future_token": (future_info or {}).get("token"),
        "future_price": (future_info or {}).get("future_price"),
        "bid_levels": bids,
        "ask_levels": asks,
        "bid_quantities": [b.get("volume") for b in bids if isinstance(b, dict)],
        "ask_quantities": [a.get("volume") for a in asks if isinstance(a, dict)],
        "provider_timestamp": provider_ts,
        "local_receive_timestamp": local_dt.isoformat(),
        "age_seconds": age,
        "trading_unit": trading_unit,
        "lot_size": contract.get("lot_size"),
        "tick_size": contract.get("tick_size"),
        "quote_payload_hash": payload_hash,
        "sample_ordinal": ordinal,
        "collection_utc": local_dt.isoformat(),
        "sdk_version": None,
    }


def _fetch_row(data_api, token):
    """One read-only FULL quote. Returns row dict or None."""
    try:
        r = data_api.getMarketData("FULL", {"MCX": [str(token)]})
    except Exception as exc:
        return None
    if not isinstance(r, dict):
        return None
    rows = (r.get("data") or {}).get("fetched") or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("symbolToken")) == str(token):
            return row
    return None


def collect_for_product(runtime, product, samples_per_contract, session_id, dry_run=False):
    """Collect calibration evidence for one MCX product. Returns row count."""
    identity = runtime.identity
    data_api = runtime.data

    try:
        resolved = identity.resolve_active(product)
    except Exception as exc:
        print(f"[{product}] identity.resolve_active raised: {type(exc).__name__}")
        return 0

    if resolved.get("status") != "OK":
        print(f"[{product}] identity not OK: {resolved.get('status')} reason={resolved.get('reason')}")
        return 0

    future_info = resolved.get("futures") or {}
    future_symbol = future_info.get("symbol")
    future_token = future_info.get("token")
    if not future_symbol or not future_token:
        print(f"[{product}] missing future symbol/token")
        return 0

    # Read futures quote to compute ATM
    fq = _fetch_row(data_api, future_token)
    if not fq:
        print(f"[{product}] futures quote unavailable")
        return 0
    try:
        future_ltp = float(fq.get("ltp", 0) or 0)
    except Exception:
        future_ltp = 0.0
    if future_ltp <= 0:
        print(f"[{product}] futures LTP non-positive")
        return 0

    future_info = dict(future_info)
    future_info["future_price"] = future_ltp

    selection = _select_atm(resolved, future_ltp)
    if not selection:
        print(f"[{product}] could not select ATM CE/PE")
        return 0
    atm, ce, pe = selection

    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _EVIDENCE_DIR / f"{product}_{session_id}.jsonl"

    count = 0
    ordinal = 0
    for side, contract in (("CE", ce), ("PE", pe)):
        if not isinstance(contract, dict):
            print(f"[{product}] {side} ATM contract missing")
            continue
        token = contract.get("token")
        if not token:
            print(f"[{product}] {side} token missing")
            continue
        for _ in range(max(1, int(samples_per_contract))):
            ordinal += 1
            local_dt = datetime.now(timezone.utc)
            row = _fetch_row(data_api, token)
            if not row:
                time.sleep(0.4)
                continue
            out_row = _emit_row(
                session_id, product, "OBSERVATION",
                contract, side, future_info, row, local_dt, ordinal,
            )
            if dry_run:
                print(f"  [dry] {product} {side} strike={contract.get('strike')} age={out_row['age_seconds']}")
            else:
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(out_row, default=str) + "\n")
            count += 1
            time.sleep(0.5)

    print(f"[{product}] collected {count} samples -> {out_path if not dry_run else '(dry-run)'}")
    return count


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", default=",".join(_SUPPORTED),
                    help="comma-separated subset of " + ",".join(_SUPPORTED))
    ap.add_argument("--samples-per-contract", type=int, default=10)
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve identities but do not write evidence")
    args = ap.parse_args(argv)

    products = tuple(p.strip().upper() for p in args.products.split(",") if p.strip())
    bad = [p for p in products if p not in _SUPPORTED]
    if bad:
        print(f"unknown products: {bad}", file=sys.stderr)
        return 2

    from services.broker.fyers_auth_v2 import (
        FyersAuthError,
        assert_fyers_token_current_v2,
        load_canonical_credentials_v2,
    )
    try:
        creds = load_canonical_credentials_v2(args.env_file)
        assert_fyers_token_current_v2(creds.access_token)
    except FyersAuthError as exc:
        print(f"AUTH_HOLD: {getattr(exc, 'reason_code', 'AUTH_MISSING')}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"AUTH_HOLD: {type(exc).__name__}", file=sys.stderr)
        return 1

    import tempfile
    from mcx.mcx_fyers_runtime_v2 import build_mcx_fyers_runtime_from_env_v2

    log_dir = tempfile.mkdtemp(prefix="mcx_calib_")
    try:
        runtime = build_mcx_fyers_runtime_from_env_v2(
            log_path=log_dir,
            env={
                "FYERS_APP_ID": creds.app_id,
                "FYERS_ACCESS_TOKEN": creds.access_token,
            },
        )
    except Exception as exc:
        print(f"RUNTIME_HOLD: {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)
        return 1

    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total = 0
    for product in products:
        n = collect_for_product(runtime, product, args.samples_per_contract,
                                session_id, dry_run=args.dry_run)
        total += n
    print(f"COLLECTION_TOTAL={total} session={session_id}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
