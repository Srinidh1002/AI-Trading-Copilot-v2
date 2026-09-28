"""Read-only MCX FYERS execution calibration collector (Option D).

Semantics:
  * Execution snapshot freshness = local observation age of a synchronous
    FYERS depth response. Not a provider timestamp. Explicit basis:
    "SYNCHRONOUS_FYERS_DEPTH_RESPONSE".
  * Provider last-trade time from the depth payload `ltt` is recorded as
    informational liquidity evidence (never used as a freshness clock).
  * FYERS does not publish a per-snapshot depth-update timestamp;
    depth_provider_timestamp_available is recorded accordingly.

Every sample records round-trip latency of the depth request, the local
observation age, and the market session status at collection time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

_EVIDENCE_DIR = REPO_ROOT / "data" / "execution_evidence" / "mcx" / "fyers"
_SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
_PROVIDER = "FYERS"

MIN_DISTINCT_HASHES_DEFAULT = 3
MAX_COLLECTION_SECONDS_DEFAULT = 150


def _utc_iso():
    return datetime.now(UTC).isoformat()


def _hash_payload(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _extract_depth(row):
    """Return (bids, asks) from a normalizer-emitted FULL row."""
    if not isinstance(row, dict):
        return [], []
    depth = row.get("depth")
    bids, asks = [], []
    if isinstance(depth, dict):
        b = depth.get("buy") or depth.get("bids") or depth.get("bid") or []
        a = depth.get("sell") or depth.get("asks") or depth.get("ask") or []
        if isinstance(b, list):
            bids = [x for x in b if isinstance(x, dict)]
        if isinstance(a, list):
            asks = [x for x in a if isinstance(x, dict)]
    if not bids:
        b = row.get("bestFiveBuyData") or []
        if isinstance(b, list):
            bids = [x for x in b if isinstance(x, dict)]
    if not asks:
        a = row.get("bestFiveSellData") or []
        if isinstance(a, list):
            asks = [x for x in a if isinstance(x, dict)]
    return bids, asks


def _level_quantity(level):
    for k in ("quantity", "volume", "qty"):
        v = level.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def _level_orders(level):
    v = level.get("orders") or level.get("ord")
    if isinstance(v, (int, float)):
        return v
    return None


def _parse_provider_ts(raw):
    """Return timezone-aware datetime (UTC) or None.

    Accepts int/float epoch seconds, epoch ms, numeric-string epoch
    seconds/milliseconds, and ISO-8601 strings.
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        v = float(raw)
        if v > 1e12:
            v = v / 1000.0
        try:
            return datetime.fromtimestamp(v, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            v = float(s)
            if v > 1e12:
                v = v / 1000.0
            if v >= 946684800:
                try:
                    return datetime.fromtimestamp(v, tz=UTC)
                except (OverflowError, OSError, ValueError):
                    pass
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    return None


def _provider_ltt_from_depth(row):
    """Return the raw FYERS depth `ltt` value if present, else None."""
    if not isinstance(row, dict):
        return None
    v = row.get("ltt")
    if v is not None and str(v).strip():
        return v
    depth = row.get("depth")
    if isinstance(depth, dict):
        v = depth.get("ltt")
        if v is not None and str(v).strip():
            return v
    return None


def _depth_is_empty(bids, asks):
    """True when every level on both sides is zero/placeholder."""
    if not bids or not asks:
        return True
    nonzero_b = any(isinstance(b.get("price"), (int, float)) and b.get("price") > 0 for b in bids)
    nonzero_a = any(isinstance(a.get("price"), (int, float)) and a.get("price") > 0 for a in asks)
    return not (nonzero_b and nonzero_a)


def _fetch_row(data_api, token):
    try:
        r = data_api.getMarketData("FULL", {"MCX": [str(token)]})
    except Exception:
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


def _emit_row(
    *,
    session_id,
    product,
    phase,
    contract,
    side,
    future_info,
    row,
    depth_request_started_at,
    depth_request_completed_at,
    depth_round_trip_ms,
    session_status,
    ordinal,
):
    bids, asks = _extract_depth(row)
    bq = [_level_quantity(x) for x in bids]
    aq = [_level_quantity(x) for x in asks]
    bo = [_level_orders(x) for x in bids]
    ao = [_level_orders(x) for x in asks]

    now_utc = datetime.now(UTC)

    depth_received_at = depth_request_completed_at
    exec_age = (now_utc - depth_received_at).total_seconds()
    if exec_age < 0:
        exec_age = 0.0

    ltt_raw = _provider_ltt_from_depth(row)
    ltt_dt = _parse_provider_ts(ltt_raw) if ltt_raw is not None else None
    if ltt_dt is not None and ltt_dt > now_utc:
        ltt_dt = None
    last_trade_age = (now_utc - ltt_dt).total_seconds() if ltt_dt is not None else None
    if last_trade_age is not None and last_trade_age < 0:
        last_trade_age = None

    row_identity = {
        "product": product,
        "symbol": contract.get("symbol"),
        "token": contract.get("token"),
        "expiry": contract.get("expiry"),
        "strike": contract.get("strike"),
        "side": side,
        "bid_levels": bids,
        "ask_levels": asks,
        "depth_received_at": depth_received_at.isoformat(),
    }
    payload_hash = _hash_payload(row_identity)

    trading_unit = None
    try:
        from mcx.mcx_contracts import PRODUCTS as _PRODUCTS

        trading_unit = (_PRODUCTS.get(product) or {}).get("trading_unit")
    except Exception:
        trading_unit = None

    raw_shape = row.get("raw_shape_v1") if isinstance(row, dict) else None

    total_buy_qty = sum(q for q in bq if isinstance(q, (int, float)))
    total_sell_qty = sum(q for q in aq if isinstance(q, (int, float)))

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
        "depth_request_started_at": depth_request_started_at.isoformat(),
        "depth_request_completed_at": depth_request_completed_at.isoformat(),
        "depth_received_at": depth_received_at.isoformat(),
        "depth_round_trip_ms": float(depth_round_trip_ms),
        "execution_snapshot_observed_at": depth_received_at.isoformat(),
        "execution_snapshot_age_seconds": exec_age,
        "depth_freshness_basis": "SYNCHRONOUS_FYERS_DEPTH_RESPONSE",
        "depth_provider_timestamp": None,
        "depth_provider_timestamp_available": False,
        "provider_last_trade_timestamp": (ltt_dt.isoformat() if ltt_dt is not None else None),
        "provider_last_trade_timestamp_raw": (str(ltt_raw) if ltt_raw is not None else None),
        "last_trade_age_seconds": last_trade_age,
        "last_trade_timestamp_source": "DEPTH:ltt" if ltt_dt is not None else None,
        "last_trade_recency_basis": ("DEPTH:ltt" if ltt_dt is not None else "UNAVAILABLE"),
        "ltp": row.get("ltp") if isinstance(row, dict) else None,
        "oi": row.get("oi") if isinstance(row, dict) else None,
        "volume": row.get("v") if isinstance(row, dict) else None,
        "bid_levels": bids,
        "ask_levels": asks,
        "bid_quantities": [q for q in bq if isinstance(q, (int, float))],
        "ask_quantities": [q for q in aq if isinstance(q, (int, float))],
        "bid_orders": [o for o in bo if isinstance(o, (int, float))],
        "ask_orders": [o for o in ao if isinstance(o, (int, float))],
        "total_buy_quantity": total_buy_qty,
        "total_sell_quantity": total_sell_qty,
        "spread": (
            (asks[0]["price"] - bids[0]["price"])
            if (
                bids
                and asks
                and isinstance(bids[0].get("price"), (int, float))
                and isinstance(asks[0].get("price"), (int, float))
            )
            else None
        ),
        "session_status_at_collection": session_status,
        "local_receive_timestamp": now_utc.isoformat(),
        "trading_unit": trading_unit,
        "lot_size": contract.get("lot_size"),
        "tick_size": contract.get("tick_size"),
        "quote_payload_hash": payload_hash,
        "depth_payload_hash": payload_hash,
        "sample_ordinal": ordinal,
        "collection_utc": now_utc.isoformat(),
        "raw_shape_v1": raw_shape,
        "sdk_version": None,
    }


def _select_atm(resolved, future_ltp):
    calls = resolved.get("calls") or {}
    puts = resolved.get("puts") or {}
    if not calls or not puts:
        return None
    strikes = sorted(set(list(calls.keys()) + list(puts.keys())))
    if not strikes:
        return None
    try:
        atm = min(strikes, key=lambda s: abs(float(s) - float(future_ltp)))
    except Exception:
        atm = strikes[len(strikes) // 2]
    ce = calls.get(atm)
    pe = puts.get(atm)
    if not isinstance(ce, dict) or not isinstance(pe, dict):
        return None
    return float(atm), ce, pe


def collect_side(
    runtime,
    data_api,
    product,
    contract,
    side,
    future_info,
    *,
    session_id,
    out_path,
    min_samples,
    min_distinct_hashes,
    timeout_seconds,
    ordinal_start,
    dry_run,
    session_status,
):
    token = contract.get("token")
    if not token:
        print(f"[{product}] {side} token missing")
        return 0, ordinal_start

    deadline = time.monotonic() + float(timeout_seconds)
    seen_hashes: set = set()
    last_hash = None
    rows_written = 0
    ordinal = ordinal_start
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 5

    while rows_written < min_samples or len(seen_hashes) < min_distinct_hashes:
        if time.monotonic() >= deadline:
            print(
                f"[{product}] {side} timeout after {rows_written} rows, "
                f"{len(seen_hashes)} distinct hashes"
            )
            break

        t0 = datetime.now(UTC)
        row = _fetch_row(data_api, token)
        t1 = datetime.now(UTC)
        if not row:
            time.sleep(0.4)
            continue

        _b, _a = _extract_depth(row)
        if _depth_is_empty(_b, _a):
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                print(
                    f"[{product}] {side}: market closed or book empty "
                    f"({consecutive_empty} consecutive zero-depth samples)"
                )
                break
            time.sleep(0.5)
            continue
        consecutive_empty = 0

        ordinal += 1
        rtt_ms = (t1 - t0).total_seconds() * 1000.0
        out = _emit_row(
            session_id=session_id,
            product=product,
            phase="OBSERVATION",
            contract=contract,
            side=side,
            future_info=future_info,
            row=row,
            depth_request_started_at=t0,
            depth_request_completed_at=t1,
            depth_round_trip_ms=rtt_ms,
            session_status=session_status,
            ordinal=ordinal,
        )
        h = out["quote_payload_hash"]
        if h != last_hash:
            seen_hashes.add(h)
            last_hash = h
        if dry_run:
            print(
                f"  [dry] {product} {side} strike={contract.get('strike')} "
                f"ltp={out['ltp']} bq={out['bid_quantities']} aq={out['ask_quantities']} "
                f"rtt_ms={rtt_ms:.0f} lt_src={out['last_trade_timestamp_source']} "
                f"lt_age={out['last_trade_age_seconds']} hash={h[:8]}"
            )
        else:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(out, default=str) + "\n")
        rows_written += 1
        if rows_written >= min_samples and len(seen_hashes) >= min_distinct_hashes:
            break
        time.sleep(0.3)

    print(f"[{product}] {side}: {rows_written} rows, {len(seen_hashes)} distinct hashes")
    return rows_written, ordinal


def collect_for_product(
    runtime,
    product,
    samples_per_contract,
    session_id,
    *,
    min_distinct_hashes=MIN_DISTINCT_HASHES_DEFAULT,
    timeout_seconds=MAX_COLLECTION_SECONDS_DEFAULT,
    dry_run=False,
):
    identity = runtime.identity
    data_api = runtime.data

    session_status = "UNKNOWN"
    try:
        from mcx.mcx_calendar import get_session as _get_session

        sess = _get_session()
        session_status = str(sess.get("status") or "UNKNOWN")
    except Exception:
        session_status = "UNKNOWN"
    print(f"[{product}] session_status={session_status}")

    try:
        resolved = identity.resolve_active(product)
    except Exception as exc:
        print(f"[{product}] identity.resolve_active raised: {type(exc).__name__}")
        return 0

    if resolved.get("status") != "OK":
        print(
            f"[{product}] identity not OK: {resolved.get('status')} reason={resolved.get('reason')}"
        )
        return 0

    future_info = resolved.get("futures") or {}
    future_token = future_info.get("token")
    if not future_token:
        print(f"[{product}] missing future token")
        return 0

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

    total_rows = 0
    ordinal = 0
    per_side = max(1, int(samples_per_contract))
    for side, contract in (("CE", ce), ("PE", pe)):
        if not isinstance(contract, dict):
            print(f"[{product}] {side} contract missing")
            continue
        n, ordinal = collect_side(
            runtime,
            data_api,
            product,
            contract,
            side,
            future_info,
            session_id=session_id,
            out_path=out_path,
            min_samples=per_side,
            min_distinct_hashes=int(min_distinct_hashes),
            timeout_seconds=float(timeout_seconds),
            ordinal_start=ordinal,
            dry_run=dry_run,
            session_status=session_status,
        )
        total_rows += n

    print(
        f"[{product}] collected {total_rows} samples -> {out_path if not dry_run else '(dry-run)'}"
    )
    return total_rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--products",
        default=",".join(_SUPPORTED),
        help="comma-separated subset of " + ",".join(_SUPPORTED),
    )
    ap.add_argument("--samples-per-contract", type=int, default=10)
    ap.add_argument("--min-distinct-hashes", type=int, default=MIN_DISTINCT_HASHES_DEFAULT)
    ap.add_argument("--timeout-seconds", type=int, default=MAX_COLLECTION_SECONDS_DEFAULT)
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve identities and print rows but do not write evidence",
    )
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
        print(
            f"AUTH_HOLD: {getattr(exc, 'reason_code', 'AUTH_MISSING')}",
            file=sys.stderr,
        )
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
        print(
            f"RUNTIME_HOLD: {type(exc).__name__}: {str(exc)[:120]}",
            file=sys.stderr,
        )
        return 1

    session_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    total = 0
    for product in products:
        n = collect_for_product(
            runtime,
            product,
            args.samples_per_contract,
            session_id,
            min_distinct_hashes=args.min_distinct_hashes,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
        total += n
    print(f"COLLECTION_TOTAL={total} session={session_id}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
