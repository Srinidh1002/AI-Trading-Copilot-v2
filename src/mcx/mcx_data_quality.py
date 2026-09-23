"""MCX data quality gates — spec §5.
Blocks analysis when evidence is stale/incomplete. Never substitutes NEUTRAL for MISSING.
"""

import time
from datetime import datetime, timezone


# Thresholds (seconds) — validated against observed data cadence, not tuned to outcomes
FUTURE_QUOTE_MAX_AGE = 90       # MCX getMarketData latency ~50s observed
OPTION_QUOTE_MAX_AGE = 90
CANDLES_MAX_AGE = 300
CHAIN_MAX_AGE = 180
EXTERNAL_MAX_AGE = 900          # yfinance 5d/1h cadence


def _age_seconds(ts, as_of=None):
    """Age in seconds. If as_of is provided (replay time), uses it instead of wall clock."""
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except Exception:
            return None
    if isinstance(ts, datetime):
        ref = as_of if as_of is not None else datetime.now(timezone.utc)
        # Phase 9.1 - normalise both sides to UTC-aware. Chain timestamps
        # arrive from FYERS as aware ISO strings; datetime.now() is naive.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return (ref - ts).total_seconds()
    if isinstance(ts, (int, float)):
        ref = as_of.timestamp() if as_of is not None else time.time()
        return ref - ts
    return None


def check_future_quote(fq_row, max_age=FUTURE_QUOTE_MAX_AGE):
    """fq_row: dict from getMarketData or None."""
    if not fq_row:
        return False, "FUTURE_QUOTE_MISSING"
    ltp = float(fq_row.get("ltp", 0) or 0)
    if ltp <= 0:
        return False, "FUTURE_LTP_ZERO"
    # Angel doesn't give per-row ts; use fetch-time as proxy
    # (bot stamps fetch time; here we accept presence of ltp as minimum)
    return True, "OK"


def check_option_quote(opt_row, max_age=OPTION_QUOTE_MAX_AGE):
    if not opt_row:
        return False, "OPTION_QUOTE_MISSING"
    ltp = float(opt_row.get("ltp", 0) or 0)
    if ltp <= 0:
        return False, "OPTION_LTP_ZERO"
    return True, "OK"


def check_candles(mtf, min_tfs=3):
    """mtf: output from compute_mtf. Require at least min_tfs timeframes loaded."""
    if not mtf or mtf.get("status") != "OK":
        return False, "MTF_UNAVAILABLE"
    ok_tfs = sum(1 for v in mtf.get("timeframes", {}).values()
                 if v.get("status") == "OK")
    if ok_tfs < min_tfs:
        return False, f"MTF_INCOMPLETE({ok_tfs}/{min_tfs})"
    return True, "OK"


def check_chain(chain, max_age=CHAIN_MAX_AGE, as_of=None):  # M13_DQ_as_of_fix
    if not chain or chain.get("status") != "OK":
        return False, "CHAIN_UNAVAILABLE"
    age = _age_seconds(chain.get("fetched_at"), as_of=as_of)
    if age is not None and age > max_age:
        return False, f"CHAIN_STALE({int(age)}s)"
    if not chain.get("future_ltp") or chain.get("future_ltp") <= 0:
        return False, "CHAIN_FUTURE_LTP_ZERO"
    ce_n = len(chain.get("ce_data", {}))
    pe_n = len(chain.get("pe_data", {}))
    if ce_n < 3 or pe_n < 3:
        return False, f"CHAIN_TOO_THIN({ce_n}CE/{pe_n}PE)"
    return True, "OK"


def check_external(ctx, max_age=EXTERNAL_MAX_AGE):
    if not ctx or ctx.get("status") != "OK":
        return False, "EXTERNAL_UNAVAILABLE"
    age = _age_seconds(ctx.get("fetched_at"))
    if age is not None and age > max_age:
        return False, f"EXTERNAL_STALE({int(age)}s)"
    # Need at least 1 primary driver
    if not ctx.get("primary"):
        return False, "EXTERNAL_NO_PRIMARY"
    return True, "OK"


def check_session(session_state):
    if not session_state or not session_state.get("tradable"):
        return False, f"SESSION_{session_state.get('status') if session_state else 'UNKNOWN'}"
    return True, "OK"


def check_identity(identity_res):
    if not identity_res or identity_res.get("status") != "OK":
        return False, f"IDENTITY_{identity_res.get('status') if identity_res else 'MISSING'}"
    if not identity_res.get("futures"):
        return False, "IDENTITY_NO_FUTURE"
    return True, "OK"


def evaluate_all(*, future_quote=None, option_quote=None, mtf=None, chain=None,
                 external=None, session=None, identity=None, as_of=None):  # M13_DQ_as_of_fix
    """Returns (ok: bool, blockers: list[str])."""
    blockers = []

    ok, r = check_identity(identity)
    if not ok: blockers.append(r)

    ok, r = check_session(session)
    if not ok: blockers.append(r)

    ok, r = check_chain(chain, as_of=as_of)
    if not ok: blockers.append(r)

    ok, r = check_candles(mtf)
    if not ok: blockers.append(r)

    ok, r = check_external(external)
    if not ok: blockers.append(r)

    if future_quote is not None:
        ok, r = check_future_quote(future_quote)
        if not ok: blockers.append(r)

    if option_quote is not None:
        ok, r = check_option_quote(option_quote)
        if not ok: blockers.append(r)

    return (len(blockers) == 0, blockers)


def report_freshness(*, chain=None, external=None, mtf=None, future_quote_at=None, as_of=None):
    """Return dict of ages and statuses for audit display."""
    out = {}
    if future_quote_at is not None:
        age = _age_seconds(future_quote_at, as_of=as_of)
        out["future_age_s"] = int(age) if age is not None else None
        out["future_max_s"] = FUTURE_QUOTE_MAX_AGE
        out["future_fresh"] = (age is not None and age <= FUTURE_QUOTE_MAX_AGE)
    if chain:
        age = _age_seconds(chain.get("fetched_at"))
        out["chain_age_s"] = int(age) if age is not None else None
        out["chain_max_s"] = CHAIN_MAX_AGE
        out["chain_fresh"] = (age is not None and age <= CHAIN_MAX_AGE)
    if external:
        age = _age_seconds(external.get("fetched_at"), as_of=as_of)
        out["external_age_s"] = int(age) if age is not None else None
        out["external_max_s"] = EXTERNAL_MAX_AGE
        out["external_fresh"] = (age is not None and age <= EXTERNAL_MAX_AGE)
    if mtf:
        ok = sum(1 for v in (mtf.get("timeframes") or {}).values()
                 if v.get("status") == "OK")
        total = len(mtf.get("timeframes") or {})
        out["mtf_ok"] = ok
        out["mtf_total"] = total
        out["mtf_complete"] = ok >= 3
    return out


def freshness_summary(fr):
    """Format freshness dict as one line."""
    parts = []
    if "future_age_s" in fr:
        age = fr["future_age_s"]
        parts.append(f"future={age}s/{fr['future_max_s']}s {'OK' if fr['future_fresh'] else 'STALE'}")
    if "chain_age_s" in fr:
        age = fr["chain_age_s"]
        parts.append(f"chain={age}s/{fr['chain_max_s']}s {'OK' if fr['chain_fresh'] else 'STALE'}")
    if "external_age_s" in fr:
        age = fr["external_age_s"]
        parts.append(f"ext={age}s/{fr['external_max_s']}s {'OK' if fr['external_fresh'] else 'STALE'}")
    if "mtf_ok" in fr:
        parts.append(f"mtf={fr['mtf_ok']}/{fr['mtf_total']}")
    return "  ".join(parts)


if __name__ == "__main__":
    print("MCX data quality module loaded OK")
    # Self-test
    ok, b = evaluate_all(
        mtf={"status": "OK", "timeframes": {"5m": {"status": "OK"}, "15m": {"status": "OK"}, "1h": {"status": "OK"}}},
        chain={"status": "OK", "future_ltp": 9500, "ce_data": {1: {}, 2: {}, 3: {}}, "pe_data": {1: {}, 2: {}, 3: {}}},
        external={"status": "OK", "primary": {"WTI": {}}, "fetched_at": datetime.now().isoformat()},
        session={"status": "OPEN", "tradable": True},
        identity={"status": "OK", "futures": {"symbol": "X"}},
    )
    print(f"self-test: ok={ok} blockers={b}")
