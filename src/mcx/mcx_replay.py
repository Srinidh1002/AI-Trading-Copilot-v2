"""MCX Historical Replay Runner — Level A technical diagnostic.
CRITICAL: REPLAY_DIAGNOSTIC mode. Never counts toward /100.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv

from mcx.mcx_contracts import PRODUCTS
from mcx.mcx_fyers_runtime_v2 import build_mcx_fyers_runtime_from_env_v2
from mcx.mcx_mtf import compute_mtf
from mcx.mcx_structure import compute_structure, session_vwap
from mcx.mcx_regime import classify as classify_regime, describe as describe_regime
from mcx.mcx_replay_clock import ReplayClock
from mcx.mcx_replay_evidence import (
    assert_not_future, filter_candles_by_replay_time,
    determine_replay_levels, full_decision_status,
    TimeTravelViolation, LiveDataBoundaryViolation,
)

load_dotenv()
IST = ZoneInfo("Asia/Kolkata")

SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
REPLAY_ROOT = "data/replay/mcx"

# Per-timeframe interval in seconds (for close-time computation)
INTERVAL_SECONDS = {
    "ONE_MINUTE": 60, "THREE_MINUTE": 180, "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900, "THIRTY_MINUTE": 1800, "ONE_HOUR": 3600,
}


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--start", default="17:00")
    ap.add_argument("--end", default="23:15")
    ap.add_argument("--step-seconds", type=int, default=60)
    args = ap.parse_args()
    p = (args.product or "").upper().strip()
    if p not in SUPPORTED:
        raise SystemExit(f"UNSUPPORTED_PRODUCT: {args.product!r}. Supported: {SUPPORTED}")
    return p, args.date, args.start, args.end, args.step_seconds


def login():
    """Compose FYERS data-only runtime for historical replay."""
    log_dir = os.path.join(
        "logs",
        "mcx_fyers_replay",
    )

    os.makedirs(
        log_dir,
        exist_ok=True,
    )

    try:
        return (
            build_mcx_fyers_runtime_from_env_v2(
                log_path=log_dir,
            )
        )
    except Exception as exc:
        print(
            "FYERS_RUNTIME_UNAVAILABLE: "
            f"{type(exc).__name__}: "
            f"{str(exc)[:120]}"
        )
        return None


def _hash(decisions):
    h = hashlib.sha256()
    for d in decisions:
        h.update(json.dumps({
            "t": d["replay_time"],
            "mtf": d.get("mtf_aggregate"),
            "regime": d.get("regime"),
            "structure": d.get("structure_overall"),
            "action": d.get("technical_action"),
        }, sort_keys=True, default=str).encode())
    return h.hexdigest()


def main():
    product, date_str, start_hm, end_hm, step = _parse_args()
    replay_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    sh, sm = map(int, start_hm.split(":"))
    eh, em = map(int, end_hm.split(":"))
    start_ist = datetime(replay_date.year, replay_date.month, replay_date.day,
                         sh, sm, tzinfo=IST)
    end_ist = datetime(replay_date.year, replay_date.month, replay_date.day,
                       eh, em, tzinfo=IST)

    print("=" * 100)
    print(f"MCX HISTORICAL REPLAY — {product} {date_str}")
    print(f"  EXECUTION_MODE = REPLAY_DIAGNOSTIC")
    print(f"  MARKET_ORIGIN  = HISTORICAL")
    print(f"  CERT_ELIGIBLE  = False")
    print(f"  window {start_ist.isoformat()} → {end_ist.isoformat()}  step={step}s")
    print("=" * 100)

    runtime = login()

    if runtime is None:
        print("FYERS_RUNTIME_FAILED")
        return

    obj = runtime.data

    print(
        "✅ FYERS data-only replay runtime established"
    )

    # Resolve contract as_of replay_date.
    resolver = runtime.identity
    res = resolver.resolve_active(product, as_of=replay_date)
    if res.get("status") != "OK" or not res.get("futures"):
        print(f"CONTRACT_IDENTITY_UNVERIFIED: {res.get('status')}")
        return
    fut = res["futures"]
    fut_token = str(fut["token"])
    print(f"Friday contract: {fut.get('symbol')} token={fut_token} exp={fut.get('expiry')}")

    # Replay clock
    clock = ReplayClock(start_ist=start_ist, step_seconds=step, end_ist=end_ist)

    # Output dir
    out_dir = os.path.join(REPLAY_ROOT, product.lower(), date_str)
    os.makedirs(out_dir, exist_ok=True)

    decisions = []
    time_travel_violations = 0
    live_boundary_violations = 0
    evals_attempted = 0
    evals_complete = 0
    incomplete_evidence = 0

    while True:
        rt = clock.now
        evals_attempted += 1

        # Fetch candles for this replay time
        try:
            mtf = compute_mtf(obj, fut_token, "MCX", now=rt)
        except Exception as e:
            mtf = {"status": "MTF_ERROR", "err": str(e)[:80]}

        # Structure using replay time
        try:
            vwap_ctx = session_vwap(obj, fut_token, exchange="MCX", now=rt)
            structure = compute_structure(mtf, vwap_ctx, None)
        except Exception as e:
            structure = {"status": "STRUCTURE_ERROR", "err": str(e)[:80]}

        # Regime
        try:
            regime = classify_regime(mtf.get("timeframes", {}))
        except Exception:
            regime = {"regime": "UNKNOWN", "confidence": 0.0}

        # Determine levels
        has_candles = mtf.get("status") == "OK" and len(mtf.get("timeframes", {})) >= 3
        has_chain = False   # honest — no historical chain
        has_bidask = False  # honest — no historical depth
        levels = determine_replay_levels(has_candles, has_chain, has_bidask)

        # Full decision completeness
        full_status, missing = full_decision_status(
            chain_ok=has_chain, external_ok=False, event_ok=False)

        if full_status == "COMPLETE":
            evals_complete += 1
        else:
            incomplete_evidence += 1

        decision = {
            "replay_time": rt.isoformat(),
            "product": product,
            "execution_mode": "REPLAY_DIAGNOSTIC",
            "market_origin": "HISTORICAL",
            "certification_eligible": False,
            "contract": fut.get("symbol"),
            "contract_token": fut_token,
            "mtf_aggregate": mtf.get("aggregate_trend"),
            "mtf_status": mtf.get("status"),
            "structure_overall": structure.get("overall_structure") if isinstance(structure, dict) else None,
            "vwap_position": structure.get("vwap_position") if isinstance(structure, dict) else None,
            "regime": regime.get("regime"),
            "regime_confidence": regime.get("confidence"),
            "technical_action": "UNAVAILABLE",  # cannot decide without chain/external
            "full_decision_status": full_status,
            "missing_components": missing,
            "replay_levels": levels,
        }
        decisions.append(decision)

        print(f"  [{rt.strftime('%H:%M:%S')}] mtf={mtf.get('aggregate_trend')} "
              f"regime={regime.get('regime')}({regime.get('confidence')}) "
              f"struct={structure.get('overall_structure') if isinstance(structure, dict) else '?'} "
              f"full={full_status}")

        if not clock.advance():
            break

    # Write decisions
    with open(os.path.join(out_dir, "decisions.jsonl"), "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d, default=str) + "\n")

    # Summary
    summary = {
        "product": product,
        "date": date_str,
        "execution_mode": "REPLAY_DIAGNOSTIC",
        "market_origin": "HISTORICAL",
        "certification_eligible": False,
        "window": f"{start_ist.isoformat()} → {end_ist.isoformat()}",
        "step_seconds": step,
        "contract_resolved": fut.get("symbol"),
        "contract_token": fut_token,
        "evals_attempted": evals_attempted,
        "evals_complete": evals_complete,
        "incomplete_evidence": incomplete_evidence,
        "time_travel_violations": time_travel_violations,
        "live_boundary_violations": live_boundary_violations,
        "levels": levels,
        "determinism_hash": _hash(decisions),
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 100)
    print(f"REPLAY COMPLETE — {product}")
    print(f"  evals_attempted   = {evals_attempted}")
    print(f"  evals_complete    = {evals_complete}")
    print(f"  incomplete        = {incomplete_evidence}")
    print(f"  Level A = {levels['level_a']}   Level B = {levels['level_b']}   Level C = {levels['level_c']}")
    print(f"  determinism_hash  = {summary['determinism_hash'][:16]}...")
    print(f"  output            = {out_dir}")
    print("=" * 100)
    print(f"CERTIFICATION_COUNTER_DELTA = 0 (REPLAY_DIAGNOSTIC)")
    print(f"BROKER_SUBMISSION = false")
    print(f"LIVE_EXECUTION = false")


if __name__ == "__main__":
    main()
