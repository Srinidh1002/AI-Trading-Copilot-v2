"""NATGAS read-only pipeline probe — F15-R2 Phase R2-14 / M6.

Read-only. No state writes. No order socket. Never prints token values.

Executes the exact MCX worker pipeline stage sequence for one product
(default NATGASMINI), timestamps each stage, and reports PASS/FAIL per
stage. Motivated by the 2026-09-28 NATGAS worker that hung for ~4.5h
inside a synchronous provider call; the F15-R1/R2 heartbeat + liveness
watchdog now detect this, and this probe proves the pipeline itself is
healthy today.

Exit codes:
    0  all required stages PASS
    1  one or more required stages FAIL

Required stages (mission R2-14):
    RUNTIME
    CALENDAR
    IDENTITY
    ACTIVE_FUTURE
    CHAIN
    MTF
    EXTERNAL
    VWAP
    DATA_QUALITY
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_env(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(str(env_file), override=False)
    except Exception:
        pass


class _Timer:
    def __init__(self):
        self.stages = {}

    def run(self, name, fn):
        t0 = time.monotonic()
        try:
            value = fn()
            ok = True
            err = None
        except Exception as e:
            value = None
            ok = False
            err = f"{type(e).__name__}: {str(e)[:200]}"
        duration = time.monotonic() - t0
        self.stages[name] = {
            "duration_seconds": round(duration, 3),
            "ok": ok,
            "error": err,
        }
        return value, ok, err


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Read-only MCX pipeline probe (PAPER/data-only)"
    )
    ap.add_argument("--product", default="NATGASMINI")
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--warn-stage-seconds", type=float, default=120.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    product = args.product.upper().strip()

    print("NATGAS_PIPELINE_PROBE_START")
    print(f"PRODUCT={product}")
    print(f"ENV_FILE={args.env_file}")
    print("DATA_ONLY=True")
    print("TOKEN_VALUES_PRINTED=False")

    _load_env(args.env_file)

    log_dir = (
        Path(args.log_dir)
        if args.log_dir
        else REPO_ROOT / "logs" / "natgas_pipeline_probe"
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"LOG_DIR={log_dir}")

    timer = _Timer()
    fails = []

    # ---------- RUNTIME ----------
    def _runtime():
        from mcx.mcx_fyers_runtime_v2 import (
            build_mcx_fyers_runtime_from_env_v2,
        )
        rt = build_mcx_fyers_runtime_from_env_v2(log_path=str(log_dir))
        if rt is None:
            raise RuntimeError("runtime is None")
        return rt

    runtime, ok, err = timer.run("RUNTIME", _runtime)
    _emit("RUNTIME", ok, err)
    if not ok:
        fails.append("RUNTIME")
        _finish(timer, fails, args, product)
        return 1

    obj = runtime.data

    # ---------- CALENDAR ----------
    def _cal():
        from mcx.mcx_calendar import get_session
        c = get_session()
        if not isinstance(c, dict):
            raise RuntimeError("calendar not a dict")
        return c

    cal, ok, err = timer.run("CALENDAR", _cal)
    _emit("CALENDAR", ok, err)
    if not ok:
        fails.append("CALENDAR")

    # ---------- IDENTITY ----------
    def _ident():
        r = runtime.identity.resolve_active(product)
        if not isinstance(r, dict) or r.get("status") != "OK":
            raise RuntimeError(
                f"identity status={r.get('status') if isinstance(r, dict) else 'MALFORMED'}"
            )
        return r

    res, ok, err = timer.run("IDENTITY", _ident)
    _emit("IDENTITY", ok, err)
    if not ok:
        fails.append("IDENTITY")
        _finish(timer, fails, args, product)
        return 1

    # ---------- ACTIVE_FUTURE ----------
    def _active_fut():
        fut = (res.get("futures") or {}) if isinstance(res, dict) else {}
        tok = str(fut.get("token") or "").strip()
        if not tok:
            raise RuntimeError("no active future token")
        return {"token": tok, "symbol": str(fut.get("symbol") or "")}

    active, ok, err = timer.run("ACTIVE_FUTURE", _active_fut)
    _emit("ACTIVE_FUTURE", ok, err)
    if not ok:
        fails.append("ACTIVE_FUTURE")
        _finish(timer, fails, args, product)
        return 1

    fut_token = active["token"]

    # ---------- CHAIN ----------
    def _chain():
        c = runtime.native_chain.build(product, window_steps=20)
        if not isinstance(c, dict) or c.get("status") != "OK":
            raise RuntimeError(
                f"chain status={c.get('status') if isinstance(c, dict) else 'MALFORMED'}"
            )
        return c

    chain, ok, err = timer.run("CHAIN", _chain)
    _emit("CHAIN", ok, err)
    if not ok:
        fails.append("CHAIN")

    # ---------- MTF ----------
    def _mtf():
        from mcx.mcx_mtf import compute_mtf
        m = compute_mtf(obj, fut_token, "MCX")
        if not isinstance(m, dict) or m.get("status") != "OK":
            raise RuntimeError(
                f"mtf status={m.get('status') if isinstance(m, dict) else 'MALFORMED'}"
            )
        return m

    mtf, ok, err = timer.run("MTF", _mtf)
    _emit("MTF", ok, err)
    if not ok:
        fails.append("MTF")

    # ---------- EXTERNAL ----------
    def _external():
        from mcx.mcx_external_context import fetch_context
        c = fetch_context(product)
        if not isinstance(c, dict):
            raise RuntimeError("external context not a dict")
        return c

    ctx, ok, err = timer.run("EXTERNAL", _external)
    _emit("EXTERNAL", ok, err)
    if not ok:
        fails.append("EXTERNAL")

    # ---------- VWAP ----------
    def _vwap():
        from mcx.mcx_structure import session_vwap
        v = session_vwap(obj, fut_token, exchange="MCX")
        if not v:
            raise RuntimeError("vwap empty")
        return v

    vwap_ctx, ok, err = timer.run("VWAP", _vwap)
    _emit("VWAP", ok, err)
    if not ok:
        fails.append("VWAP")

    # ---------- DATA_QUALITY ----------
    def _dq():
        from mcx.mcx_data_quality import evaluate_all as quality_evaluate
        ok_flag, blockers = quality_evaluate(
            mtf=mtf,
            chain=chain,
            external=ctx,
            session=cal,
            identity=res,
            future_quote=None,
        )
        if not ok_flag:
            raise RuntimeError(f"dq blockers={blockers}")
        return {"ok": True, "blockers": blockers}

    dq, ok, err = timer.run("DATA_QUALITY", _dq)
    _emit("DATA_QUALITY", ok, err)
    if not ok:
        fails.append("DATA_QUALITY")

    _finish(timer, fails, args, product)
    return 0 if not fails else 1


def _emit(name, ok, err):
    print(f"{name}={('PASS' if ok else 'FAIL')}")
    if err:
        print(f"{name}_ERROR={err}")


def _finish(timer, fails, args, product):
    # Warning pass for slow-but-complete stages
    slow = [
        f"{n}={info['duration_seconds']}s"
        for n, info in timer.stages.items()
        if info["duration_seconds"] > args.warn_stage_seconds
    ]
    print("")
    for name in (
        "RUNTIME", "CALENDAR", "IDENTITY", "ACTIVE_FUTURE",
        "CHAIN", "MTF", "EXTERNAL", "VWAP", "DATA_QUALITY",
    ):
        info = timer.stages.get(name)
        if info is None:
            continue
        print(f"{name}_DURATION_SECONDS={info['duration_seconds']}")
    total = round(sum(i["duration_seconds"] for i in timer.stages.values()), 3)
    print(f"TOTAL_PIPELINE_DURATION_SECONDS={total}")
    if slow:
        print(f"SLOW_STAGES={slow}")

    overall = "PASS" if not fails else "FAIL"
    print("")
    print(f"NATGAS_PIPELINE_PROBE={overall}")
    print(f"FAILED_STAGES={fails if fails else 'none'}")
    print("TOKEN_VALUES_PRINTED=False")

    if args.json:
        print("")
        print(json.dumps({
            "product": product,
            "stages": timer.stages,
            "failed": fails,
            "finished_at_utc": datetime.now(UTC).isoformat(),
        }, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
