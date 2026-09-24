"""Canonical morning preflight + PAPER supervisor launcher.

Usage:
  python fyers_daily_auth.py --env-file .env
  python tools/preflight_and_start_five_market_paper.py                # launches
  python tools/preflight_and_start_five_market_paper.py --dry-run      # checks only

Every safety gate is verified before any worker is spawned:
  * repo root, branch (optional), .env presence
  * FYERS token freshness via assert_fyers_token_current_v2
  * PAPER-only safety flags all false
  * supervisor lock + all 5 worker locks available
  * cross-process rate-limiter state readable, no corruption
  * per-market certification authority (HOLD markets dropped)
  * per-market state file authority (index/MCX load contract)
  * per-market session calendar authority (calendar HOLD markets dropped)
  * MCX execution calibration (product-scoped, verified)
  * FYERS provider health, one read-only call per surviving market

Zero ready markets is not an error: prints HOLD summary, exits 0.
Infrastructure failure (env, locks, limiter, repo) exits 1.
Never prints tokens, secrets, or auth codes.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_DEFAULT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")

_MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
_INDEX_MARKETS = {"NIFTY", "SENSEX"}
_MCX_MARKETS = {"CRUDEOILM", "GOLDM", "NATGASMINI"}


# ---------------------------------------------------------------- helpers

def _log(tag, msg):
    print(f"[{tag:8s}] {msg}")


def _section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- checks

def check_repo(args):
    repo = Path(args.repo_root).resolve()
    if not repo.is_dir():
        return False, f"repo root missing: {repo}"
    if not (repo / "run_nifty.py").is_file():
        return False, "repo root does not contain run_nifty.py"
    if args.require_branch:
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(repo), text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except Exception as exc:
            return False, f"git branch read failed: {type(exc).__name__}"
        if out != args.require_branch:
            return False, f"branch is {out}, expected {args.require_branch}"
    return True, str(repo)


def check_env_file(env_file):
    p = Path(env_file)
    if not p.is_file():
        return False, f"env file missing: {p}", None
    try:
        from services.broker.fyers_auth_v2 import (
            FyersAuthError,
            assert_fyers_token_current_v2,
            load_canonical_credentials_v2,
        )
    except Exception as exc:
        return False, f"auth import failed: {type(exc).__name__}", None
    # Canonical read: only the named .env file, never parent process env.
    # A stale inherited FYERS_ACCESS_TOKEN or FYERS_APP_ID cannot win.
    try:
        creds = load_canonical_credentials_v2(str(p))
    except FyersAuthError as exc:
        return False, f"credential load failed: {getattr(exc, 'reason_code', 'AUTH_MISSING')}", None
    except Exception as exc:
        return False, f"credential load failed: {type(exc).__name__}", None
    try:
        assert_fyers_token_current_v2(creds.access_token)
    except FyersAuthError as exc:
        return False, f"token invalid: {getattr(exc, 'reason_code', 'AUTH')}", None
    except Exception as exc:
        return False, f"token check failed: {type(exc).__name__}", None
    return True, "token fresh", creds


def check_paper_flags():
    """Prove PAPER-only authority before any worker is spawned.

    Env-var checks only. Runtime attribute checks (data_only,
    order_capability_allowed, automatic_fallback_allowed) are enforced
    by the FYERS client and runtime builders themselves, and are
    additionally verified in check_provider_health where the objects are
    already instantiated for a read-only health probe.
    """
    bad = []
    for name in (
        "BROKER_SUBMISSION", "BROKER_SUBMISSION_ENABLED",
        "LIVE_EXECUTION", "LIVE_EXECUTION_ENABLED",
        "LIVE_EXECUTION_ELIGIBLE",
    ):
        v = str(os.environ.get(name, "")).strip().lower()
        if v in ("1", "true", "yes", "on", "enabled"):
            bad.append(name)
    if bad:
        return False, "unsafe flags: " + ",".join(bad)

    mode = str(os.environ.get("EXECUTION_MODE", "PAPER")).strip().upper()
    if mode not in ("", "PAPER"):
        return False, f"EXECUTION_MODE={mode} (must be PAPER)"

    data_only = str(os.environ.get("FYERS_DATA_ONLY", "true")).strip().lower()
    if data_only in ("0", "false", "no", "off", "disabled"):
        return False, "FYERS_DATA_ONLY is disabled"

    return True, "PAPER-only"


def check_locks(markets):
    try:
        from services.paper_orchestration.worker_lock_v2 import (
            market_worker_available,
        )
    except Exception as exc:
        return {}, f"worker_lock import failed: {type(exc).__name__}"
    verdicts = {}
    for m in markets:
        try:
            verdicts[m] = bool(market_worker_available(m))
        except Exception:
            verdicts[m] = False
    # supervisor lock probe
    try:
        from services.paper_orchestration.process_lock_v2 import lock_available
        from services.paper_orchestration.supervisor_lock_v2 import LOCK_PATH
        sup_ok = bool(lock_available(str(LOCK_PATH), role="PREFLIGHT_PROBE"))
    except Exception:
        sup_ok = False
    return {"supervisor": sup_ok, **verdicts}, ""


def check_rate_limiter():
    try:
        from src.rate_limiter import FyersRateLimitCoordinator
    except Exception as exc:
        return False, f"limiter import failed: {type(exc).__name__}"
    try:
        c = FyersRateLimitCoordinator(worker_name="preflight")
        _ = c.stats()
    except Exception as exc:
        return False, f"limiter self-check failed: {type(exc).__name__}"
    return True, "limiter ok"


def check_cert_authority(markets):
    try:
        from services.paper_orchestration.certification_halt_v2 import market_state
    except Exception as exc:
        return {m: (False, f"cert import failed: {type(exc).__name__}") for m in markets}
    out = {}
    for m in markets:
        st = market_state(m)
        if st.status == "HOLD":
            out[m] = (False, f"CERT_HOLD:{st.reason}")
        elif st.status == "COMPLETE":
            out[m] = (False, f"CERT_COMPLETE:{st.counter}")
        else:
            out[m] = (True, f"counter={st.counter}")
    return out


def check_state_authority(markets, repo_root):
    """Strict read-only state authority check via the shared validator.

    Never mutates state. Uses the caller-supplied repo_root so
    --repo-root cannot be silently ignored in favor of the module default.
    """
    from services.paper_orchestration.state_authority_readonly_v2 import (
        validate_markets,
    )
    verdicts = validate_markets(Path(repo_root).resolve(), markets)
    out = {}
    for m, v in verdicts.items():
        label = v.reason + (f"|{v.note}" if v.note else "")
        out[m] = (v.ok, label)
    return out


def check_calendar(markets, now):
    try:
        from services.paper_orchestration.worker_session_authority_v2 import (
            authority_for,
        )
        from services.paper_orchestration.automated_paper_supervisor_v2 import (
            WORKERS_V2,
        )
    except Exception as exc:
        return {m: (False, f"cal import failed: {type(exc).__name__}") for m in markets}
    specs = {s.name: s for s in WORKERS_V2}
    out = {}
    for m in markets:
        spec = specs.get(m)
        if spec is None:
            out[m] = (False, "spec missing")
            continue
        auth = authority_for(spec, now)
        if not auth.calendar_authoritative:
            out[m] = (False, f"CALENDAR_HOLD:{auth.status}")
        else:
            out[m] = (True, auth.status)
    return out


def _calibration_status_for(product):
    """Read-only accessor, monkeypatchable for tests.

    Returns a dict with at minimum: calibration_valid, provider_scoped,
    quantity_verified, freshness_calibrated, entry_execution_calibrated,
    evidence_kind, calibration_provider, reason. Never mutates config.
    """
    try:
        from mcx.mcx_exec_config import (
            calibration_status as _cal_status,
            get_provider_product_config as _get_cfg,
        )
    except Exception as exc:
        return {
            "calibration_valid": False,
            "reason": f"CALIBRATION_API_UNAVAILABLE:{type(exc).__name__}",
        }
    try:
        r = _cal_status(product)
    except Exception as exc:
        return {
            "calibration_valid": False,
            "reason": f"CALIBRATION_RAISED:{type(exc).__name__}",
        }
    if not isinstance(r, dict):
        return {"calibration_valid": False, "reason": "CALIBRATION_SCHEMA_INVALID"}
    # Enrich with evidence_kind / calibration_provider from the underlying record
    try:
        raw = _get_cfg(product)
        if isinstance(raw, dict):
            r = dict(r)
            r["evidence_kind"] = raw.get("evidence_kind")
            r["calibration_provider"] = (
                raw.get("calibration_provider")
                or raw.get("provider")
            )
    except Exception:
        pass
    if "reason" not in r:
        r = dict(r)
        r["reason"] = "UNSPECIFIED"
    return r


def check_calibration(markets):
    """Strict MCX calibration gate.

    A product is admitted only when every flag below is true AND the
    evidence kind is LIVE_MARKET_DEPTH AND the provider is FYERS.
    calibration_valid=True alone is not sufficient.
    """
    out = {}
    for m in markets:
        if m not in _MCX_MARKETS:
            out[m] = (True, "n/a (index)")
            continue
        r = _calibration_status_for(m)
        reason = str(r.get("reason") or "?")
        checks = [
            ("calibration_valid", r.get("calibration_valid")),
            ("provider_scoped", r.get("provider_scoped")),
            ("quantity_verified", r.get("quantity_verified")),
            ("freshness_calibrated", r.get("freshness_calibrated")),
            ("entry_execution_calibrated", r.get("entry_execution_calibrated")),
        ]
        missing = [name for name, val in checks if not bool(val)]
        if missing:
            out[m] = (False,
                      f"CALIBRATION_MISSING:{reason}|missing={','.join(missing)}")
            continue
        evk = str(r.get("evidence_kind") or "").upper()
        if evk != "LIVE_MARKET_DEPTH":
            out[m] = (False, f"CALIBRATION_EVIDENCE_KIND:{evk or 'NONE'}")
            continue
        prov = str(r.get("calibration_provider") or "").upper()
        if prov != "FYERS":
            out[m] = (False, f"CALIBRATION_PROVIDER_MISMATCH:{prov or 'NONE'}")
            continue
        out[m] = (True, "calibrated")
    return out


def check_provider_health(creds, markets):
    """Read-only provider health probe, one call per surviving market.

    INDEX markets use the single-symbol health helper.
    MCX markets use a data-only FYERS runtime: resolve the product
    identity and fetch one FULL market-data row for the resolved
    futures token. No order capability, no fallback.
    """
    out = {}
    index_syms = {
        "NIFTY": "NSE:NIFTY50-INDEX",
        "SENSEX": "BSE:SENSEX-INDEX",
    }
    index_markets = [m for m in markets if m in index_syms]
    mcx_markets = [m for m in markets if m in _MCX_MARKETS]

    if index_markets:
        try:
            from services.broker.fyers_provider_runtime_v2 import (
                check_fyers_provider_health_v2,
            )
            from services.broker.fyers_sdk_data_client_v2 import (
                build_fyers_data_client_v2,
            )
            import tempfile
            client = build_fyers_data_client_v2(
                client_id=creds.app_id,
                access_token=creds.access_token,
                log_path=tempfile.mkdtemp(prefix="preflight_health_"),
            )
            # Part 11: prove the data-only runtime attributes at instantiation
            if getattr(client, "data_only", None) is not True:
                raise RuntimeError("INDEX_CLIENT_NOT_DATA_ONLY")
            if getattr(client, "order_capability_allowed", None) is not False:
                raise RuntimeError("INDEX_CLIENT_ORDER_CAPABILITY_ENABLED")
            if getattr(client, "automatic_fallback_allowed", None) is not False:
                raise RuntimeError("INDEX_CLIENT_FALLBACK_ENABLED")
        except Exception as exc:
            for m in index_markets:
                out[m] = (
                    False,
                    f"health: INDEX_PROVIDER_SETUP_FAILED:{type(exc).__name__}",
                )
            client = None
        if client is not None:
            for m in index_markets:
                try:
                    h = check_fyers_provider_health_v2(client, symbol=index_syms[m])
                except Exception as exc:
                    out[m] = (False, f"health: INDEX_HEALTH_RAISED:{type(exc).__name__}")
                    continue
                if h.ok:
                    out[m] = (True, f"health: OK symbol={h.symbol}")
                else:
                    out[m] = (False, f"health: PROVIDER_HEALTH:{h.reason_code}")

    if mcx_markets:
        try:
            from mcx.mcx_fyers_runtime_v2 import (
                build_mcx_fyers_runtime_from_env_v2,
            )
            import tempfile
            log_dir = tempfile.mkdtemp(prefix="preflight_mcx_health_")
            runtime = build_mcx_fyers_runtime_from_env_v2(
                log_path=log_dir,
                env={
                    "FYERS_APP_ID": creds.app_id,
                    "FYERS_ACCESS_TOKEN": creds.access_token,
                },
            )
            if getattr(runtime, "data_only", None) is not True:
                raise RuntimeError("MCX_RUNTIME_NOT_DATA_ONLY")
            if getattr(runtime, "order_capability_allowed", None) is not False:
                raise RuntimeError("MCX_RUNTIME_ORDER_CAPABILITY_ENABLED")
            if getattr(runtime, "automatic_fallback_allowed", None) is not False:
                raise RuntimeError("MCX_RUNTIME_FALLBACK_ENABLED")
        except Exception as exc:
            for m in mcx_markets:
                out[m] = (
                    False,
                    f"health: MCX_PROVIDER_SETUP_FAILED:{type(exc).__name__}",
                )
            runtime = None

        if runtime is not None:
            for m in mcx_markets:
                try:
                    ident = runtime.identity.resolve_active(m)
                except Exception as exc:
                    out[m] = (False, f"health: MCX_IDENTITY_RAISED:{type(exc).__name__}")
                    continue
                if not isinstance(ident, dict) or ident.get("status") != "OK":
                    status = (ident or {}).get("status") if isinstance(ident, dict) else None
                    reason = (ident or {}).get("reason") if isinstance(ident, dict) else None
                    out[m] = (False, f"health: MCX_IDENTITY:{status}:{reason}")
                    continue
                fut_token = str((ident.get("futures") or {}).get("token") or "").strip()
                if not fut_token:
                    out[m] = (False, "health: MCX_FUTURE_TOKEN_MISSING")
                    continue
                try:
                    r = runtime.data.getMarketData("FULL", {"MCX": [fut_token]})
                except Exception as exc:
                    out[m] = (False, f"health: MCX_QUOTE_RAISED:{type(exc).__name__}")
                    continue
                rows = (r.get("data") or {}).get("fetched") if isinstance(r, dict) else None
                if not isinstance(rows, list) or not rows:
                    out[m] = (False, "health: MCX_NO_QUOTE_ROWS")
                    continue
                out[m] = (True, f"health: OK mcx product={m} rows={len(rows)}")

    return out


def _summarize(cert, state, cal, calibration, health, locks, requested=None):
    """Summarize over the requested markets only.

    If the operator passed --markets NIFTY,SENSEX, only those two are
    considered. Other markets having no verdict is expected, not a HOLD.
    """
    ready, held = [], {}
    markets = tuple(requested) if requested is not None else _MARKETS
    for m in markets:
        reasons = []
        for table, label in (
            (cert, "cert"),
            (state, "state"),
            (cal, "calendar"),
            (calibration, "calibration"),
            (health, "health"),
        ):
            # Health table defaults to non-failure; other tables default to failure
            default = (True, "not probed") if table is health else (False, "no verdict")
            ok, why = table.get(m, default)
            if not ok:
                reasons.append(f"{label}: {why}")
        if not locks.get(m, False):
            reasons.append("lock: WORKER_LOCK_HELD")
        if reasons:
            held[m] = "; ".join(reasons)
        else:
            ready.append(m)
    return ready, held


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=str(REPO_DEFAULT))
    ap.add_argument("--env-file", default=None,
                    help="default: <repo-root>/.env")
    ap.add_argument("--python-exe", default=sys.executable)
    ap.add_argument("--require-branch", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="run every check but do not launch the supervisor")
    ap.add_argument("--allow-partial", action="store_true",
                    help="permit launching a subset of markets when some are held")
    ap.add_argument("--markets", default=None,
                    help="comma-separated subset; default all five")
    args = ap.parse_args(argv)

    args.env_file = args.env_file or str(Path(args.repo_root) / ".env")
    now = datetime.now(IST)

    # requested markets filter (validated, deduped)
    if args.markets:
        seen, req = set(), []
        for t in args.markets.split(","):
            t = t.strip().upper()
            if t and t not in seen:
                seen.add(t)
                req.append(t)
        bad = [m for m in req if m not in _MARKETS]
        if bad:
            print(f"--markets: unknown {bad}", file=sys.stderr)
            return 2
        requested = tuple(req) if req else _MARKETS
    else:
        requested = _MARKETS

    # infrastructure checks — fail the whole run on any of these
    _section("PREFLIGHT — INFRASTRUCTURE")
    ok, detail = check_repo(args)
    _log("REPO", f"{'OK' if ok else 'FAIL'} {detail}")
    if not ok:
        print("PREFLIGHT=HOLD")
        return 1

    ok, detail, creds = check_env_file(args.env_file)
    _log("AUTH", f"{'OK' if ok else 'FAIL'} {detail}")
    if not ok:
        print("PREFLIGHT=HOLD")
        return 1

    ok, detail = check_paper_flags()
    _log("PAPER", f"{'OK' if ok else 'FAIL'} {detail}")
    if not ok:
        print("PREFLIGHT=HOLD")
        return 1

    locks, lock_err = check_locks(requested)
    sup_lock = locks.get("supervisor", False)
    _log("SUPLOCK", f"{'OK' if sup_lock else 'FAIL'}")
    if not sup_lock:
        print("PREFLIGHT=HOLD")
        return 1

    ok, detail = check_rate_limiter()
    _log("LIMITER", f"{'OK' if ok else 'FAIL'} {detail}")
    if not ok:
        print("PREFLIGHT=HOLD")
        return 1

    # per-market checks
    _section("PREFLIGHT — PER-MARKET AUTHORITY")
    cert = check_cert_authority(requested)
    state = check_state_authority(requested, args.repo_root)
    cal = check_calendar(requested, now)
    calibration = check_calibration(requested)

    # provider health only for markets that passed everything so far
    pre_ready = [
        m for m in requested
        if cert.get(m, (False,))[0]
        and state.get(m, (False,))[0]
        and cal.get(m, (False,))[0]
        and calibration.get(m, (False,))[0]
        and locks.get(m, False)
    ]
    health = check_provider_health(creds, pre_ready) if pre_ready else {}

    for m in requested:
        ok_c, why_c = cert.get(m, (False, "?"))
        ok_s, why_s = state.get(m, (False, "?"))
        ok_k, why_k = cal.get(m, (False, "?"))
        ok_l, why_l = calibration.get(m, (False, "?"))
        ok_h, why_h = health.get(m, (True, "not probed"))
        tag = "OK" if all([ok_c, ok_s, ok_k, ok_l, ok_h]) else "HOLD"
        _log(m, f"{tag} cert={why_c} state={why_s} cal={why_k} "
                f"cali={why_l} health={why_h} lock={locks.get(m, False)}")

    ready, held = _summarize(cert, state, cal, calibration, health, locks, requested)

    _section("PREFLIGHT SUMMARY")
    if ready and not held:
        verdict = "NOMINAL"
    elif ready:
        verdict = "PARTIAL"
    else:
        verdict = "HOLD"
    print(f"PREFLIGHT={verdict}")
    print(f"READY_MARKETS={','.join(ready) if ready else '-'}")
    print(f"HELD_MARKETS={','.join(held.keys()) if held else '-'}")
    for m, why in held.items():
        print(f"HOLD_REASON[{m}]={why}")

    # Return contract (Part 12):
    #   0  = launched supervisor / dry-run ready
    #   1  = infrastructure failure (repo, env, token, locks, limiter)
    #   2  = argument error
    #   10 = HOLD: zero safe markets
    #   11 = PARTIAL: subset ready and --allow-partial not supplied
    if verdict == "HOLD":
        print("SUPERVISOR_STARTED=False")
        print("EXIT_CODE=10")
        return 10
    if verdict == "PARTIAL" and not args.allow_partial:
        print("SUPERVISOR_STARTED=False")
        print("EXIT_CODE=11 (pass --allow-partial to launch subset)")
        return 11

    started = False

    cmd = [args.python_exe, "-m",
           "services.paper_orchestration.automated_paper_supervisor_v2",
           "--markets", ",".join(ready)]
    if args.dry_run:
        print(f"DRY_RUN: would exec: {' '.join(cmd)}")
        print("SUPERVISOR_STARTED=False")
        return 0

    print(f"LAUNCHING supervisor --markets {','.join(ready)}")
    try:
        rc = subprocess.call(cmd, cwd=str(Path(args.repo_root)))
    except Exception as exc:
        print(f"SUPERVISOR_STARTED=False LAUNCH_ERROR={type(exc).__name__}")
        return 1
    started = True
    print(f"SUPERVISOR_STARTED={started}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
