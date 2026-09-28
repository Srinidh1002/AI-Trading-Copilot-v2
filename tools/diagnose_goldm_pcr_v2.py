"""GOLDM StablePCR read-only diagnostic — F15-R2 Phase R2-6.

Purpose: collect evidence for R2-7 / R2-8. Never modifies state. Never
places orders. Never prints secrets.

Run:
    python tools/diagnose_goldm_pcr_v2.py [--json] [--env-file .env]

Exit codes:
    0  diagnostic ran to completion (regardless of PCR status)
    1  runtime / identity / chain unavailable
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

IST = timezone(timedelta(hours=5, minutes=30))
PRODUCT = "GOLDM"


def _load_env_file(env_file):
    """Load .env without printing anything. Missing file is not fatal."""
    try:
        from dotenv import load_dotenv
        load_dotenv(str(env_file), override=False)
    except Exception:
        pass


def _float_set(keys):
    out = set()
    for k in keys:
        try:
            out.add(float(k))
        except (TypeError, ValueError):
            pass
    return out


def compute_report(chain, product_cfg, universe_steps):
    """Pure evidence extraction. `chain` is the native chain dict."""
    ce = chain.get("ce_data") or {}
    pe = chain.get("pe_data") or {}
    fut = chain.get("future_ltp")
    max_pain = chain.get("max_pain")
    atm = chain.get("atm")

    step = float(product_cfg["strike_interval"])

    # Production anchors the reference to max_pain when available,
    # else rounds the future LTP. Mirror that here.
    if max_pain:
        reference = float(max_pain)
    elif fut:
        reference = round(float(fut) / step) * step
    else:
        reference = None

    if reference is None:
        return {
            "status": "NO_REFERENCE",
            "reference_strike": None,
        }

    nominal = [reference + i * step for i in range(-universe_steps, universe_steps + 1)]

    listed_ce = sorted(_float_set(ce.keys()))
    listed_pe = sorted(_float_set(pe.keys()))
    paired = sorted(set(listed_ce) & set(listed_pe))
    unpaired_ce = sorted(set(listed_ce) - set(listed_pe))
    unpaired_pe = sorted(set(listed_pe) - set(listed_ce))

    listed_all = set(listed_ce) | set(listed_pe)
    eligible_listed = sorted(s for s in nominal if s in listed_all)

    observed_ce = sum(1 for s in nominal if s in set(listed_ce))
    observed_pe = sum(1 for s in nominal if s in set(listed_pe))
    observed_total = observed_ce + observed_pe

    # Expected assumes the listed strikes could each contribute CE and PE.
    expected_total = 2 * len(eligible_listed)
    coverage_pct = (
        round(observed_total / expected_total * 100.0, 2)
        if expected_total > 0
        else 0.0
    )

    ref_normalized = reference in listed_ce or reference in listed_pe
    ref_as_str = str(int(reference)) in ce or str(int(reference)) in pe
    key_types = {
        "ce_first_key_type": type(next(iter(ce))).__name__ if ce else "NONE",
        "pe_first_key_type": type(next(iter(pe))).__name__ if pe else "NONE",
    }

    return {
        "status": "OK",
        "future_ltp": fut,
        "atm": atm,
        "expiry": chain.get("expiry"),
        "max_pain": max_pain,
        "reference_strike": reference,
        "raw_chain_ce": len(ce),
        "raw_chain_pe": len(pe),
        "raw_chain_total": len(ce) + len(pe),
        "listed_ce_strikes": listed_ce,
        "listed_pe_strikes": listed_pe,
        "paired_strikes": paired,
        "unpaired_ce_strikes": unpaired_ce,
        "unpaired_pe_strikes": unpaired_pe,
        "requested_reference_window": 2 * universe_steps + 1,
        "eligible_listed_reference_strikes": eligible_listed,
        "observed_eligible_ce": observed_ce,
        "observed_eligible_pe": observed_pe,
        "observed_eligible_contracts": observed_total,
        "expected_eligible_contracts": expected_total,
        "coverage_pct": coverage_pct,
        "key_types": key_types,
        "reference_key_normalized": ref_normalized,
        "reference_as_str_present": ref_as_str,
        "raw_pcr": chain.get("pcr_oi"),
        "identity_mismatch_count": chain.get("identity_mismatch_count"),
    }


def _emit_text(report, pcr_result):
    print("GOLDM_PCR_DIAGNOSTIC_START")
    for k, v in report.items():
        if k == "status":
            continue
        if isinstance(v, list) and len(v) > 20:
            print(f"{k.upper()}=first5={v[:5]} last5={v[-5:]} count={len(v)}")
        else:
            print(f"{k.upper()}={v}")
    print(f"STABLE_PCR_STATUS={pcr_result.get('status')}")
    print(f"STABLE_PCR_VALUE={pcr_result.get('PCR_EMA_3')}")
    print(f"PCR_REASON={pcr_result.get('reason')}")
    print("GOLDM_PCR_DIAGNOSTIC_END")


def _fail(report, code, note="", as_json=False):
    report["status"] = code
    report["note"] = note
    if as_json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"GOLDM_PCR_DIAGNOSTIC_FAIL={code} note={note}")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="GOLDM PCR read-only diagnostic (PAPER-only).")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = {"product": PRODUCT, "started_at": datetime.now(IST).isoformat()}

    _load_env_file(args.env_file)

    log_dir = (
        Path(args.log_dir)
        if args.log_dir
        else Path(args.repo_root).resolve() / "logs" / "goldm_pcr_diagnostic"
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        from mcx.mcx_contracts import PRODUCTS
        from mcx.mcx_fyers_runtime_v2 import build_mcx_fyers_runtime_from_env_v2
        from mcx.mcx_pcr import UNIVERSE_STEPS, StablePCR
    except Exception as exc:
        return _fail(report, "IMPORT_FAILED", f"{type(exc).__name__}", args.json)

    try:
        runtime = build_mcx_fyers_runtime_from_env_v2(log_path=str(log_dir))
    except Exception as exc:
        return _fail(report, "RUNTIME_RAISED", type(exc).__name__, args.json)
    if runtime is None:
        return _fail(report, "RUNTIME_UNAVAILABLE", "", args.json)

    try:
        res = runtime.identity.resolve_active(PRODUCT)
    except Exception as exc:
        return _fail(report, "IDENTITY_RAISED", type(exc).__name__, args.json)
    if not isinstance(res, dict) or res.get("status") != "OK":
        _istat = res.get("status") if isinstance(res, dict) else "MALFORMED"
        return _fail(report, f"IDENTITY_{_istat}", "", args.json)

    try:
        chain = runtime.native_chain.build(PRODUCT, window_steps=20)
    except Exception as exc:
        return _fail(report, "CHAIN_RAISED", type(exc).__name__, args.json)
    if not isinstance(chain, dict) or chain.get("status") != "OK":
        return _fail(
            report,
            f"CHAIN_{chain.get('status') if isinstance(chain, dict) else 'MALFORMED'}",
            chain.get("reason", "") if isinstance(chain, dict) else "",
            args.json,
        )

    report = compute_report(chain, PRODUCTS[PRODUCT], UNIVERSE_STEPS)
    report["started_at"] = datetime.now(IST).isoformat()

    # Reproduce production PCR anchor exactly.
    spcr = StablePCR(
        strike_step=PRODUCTS[PRODUCT]["strike_interval"],
        epoch="DIAGNOSTIC_ONLY",
    )
    ref = report.get("reference_strike")
    if ref is not None:
        spcr.reference_strike = ref
    pcr_result = spcr.compute(chain)

    if args.json:
        out = dict(report)
        out["stable_pcr"] = pcr_result
        print(json.dumps(out, indent=2, default=str))
    else:
        _emit_text(report, pcr_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
