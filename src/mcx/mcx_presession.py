"""MCX pre-session intelligence report — spec §30.
Establishes baseline before market opens. Does NOT trigger trades.
"""
from datetime import datetime, timedelta


def fetch_previous_session(obj, token, exchange="MCX"):
    """Pull previous session's 1h candles for prev-day H/L/C."""
    try:
        now = datetime.now()
        # Previous day 09:00 to 23:30
        prev = now - timedelta(days=1)
        while prev.weekday() >= 5:
            prev = prev - timedelta(days=1)
        frm = prev.strftime("%Y-%m-%d 09:00")
        to = prev.strftime("%Y-%m-%d 23:30")
        resp = obj.getCandleData({
            "exchange": exchange, "symboltoken": str(token),
            "interval": "ONE_HOUR", "fromdate": frm, "todate": to,
        })
        if not resp or not resp.get("data"):
            return {"status": "PREV_SESSION_UNAVAILABLE"}
        rows = resp["data"]
        highs = [float(r[2]) for r in rows]
        lows = [float(r[3]) for r in rows]
        return {
            "status": "OK",
            "prev_open": float(rows[0][1]),
            "prev_high": max(highs),
            "prev_low": min(lows),
            "prev_close": float(rows[-1][4]),
            "bars": len(rows),
        }
    except Exception as e:
        return {"status": "PREV_SESSION_ERROR", "err": str(e)[:80]}


def build_report(chain, ctx, mtf, regime, prev_session, calendar_state,
                 expiry_state, event_state, product=None):
    """Assemble pre-session intelligence dict."""
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "execution_mode": "PAPER",
        "broker_submission": False,
        "product": product,
    }

    report["session"] = calendar_state
    report["expiry"] = expiry_state
    report["event_risk"] = event_state

    if chain and chain.get("status") == "OK":
        report["contract"] = {
            "future": chain.get("future"),
            "option_expiry": chain.get("expiry"),
            "atm": chain.get("atm"),
            "future_ltp": chain.get("future_ltp"),
        }
        report["chain_metrics"] = {
            "pcr_oi": chain.get("pcr_oi"),
            "max_pain": chain.get("max_pain"),
            "resistance": chain.get("resistance"),
            "support": chain.get("support"),
        }

    if prev_session and prev_session.get("status") == "OK":
        report["previous_session"] = prev_session

    if ctx and ctx.get("status") == "OK":
        report["external"] = {
            "composite_regime": ctx.get("composite_regime"),
            "composite_pct": ctx.get("composite_move_1d_pct"),
            "primary": {k: {"regime": v.get("regime"), "chg_1": v.get("chg_1")}
                        for k, v in ctx.get("primary", {}).items()},
            "cross_asset": {k: {"regime": v.get("regime"), "chg_1": v.get("chg_1")}
                            for k, v in ctx.get("cross_asset", {}).items()},
        }

    if mtf and mtf.get("status") == "OK":
        report["mtf_aggregate"] = mtf.get("aggregate_trend")
        report["mtf_score"] = mtf.get("aggregate_score")

    if regime:
        report["regime"] = regime.get("regime")
        report["regime_confidence"] = regime.get("confidence")

    # Overnight bias (informational only, never triggers)
    ext_reg = (ctx or {}).get("composite_regime", "UNKNOWN")
    mtf_agg = (mtf or {}).get("aggregate_trend", "UNKNOWN")
    if "BULLISH" in ext_reg and "BULLISH" in mtf_agg:
        report["overnight_bias"] = "BULLISH"
    elif "BEARISH" in ext_reg and "BEARISH" in mtf_agg:
        report["overnight_bias"] = "BEARISH"
    else:
        report["overnight_bias"] = "NEUTRAL"

    report["plan"] = "WAIT FOR LIVE CONFIRMATION"
    report["note"] = "Pre-session is context only. No entry authority."
    return report


def print_report(r, product=None):
    product = product or r.get("product") or "MCX"
    print("=" * 100)
    print(format_header(product))
    print("=" * 100)
    print(f"TIME             {r.get('timestamp')}")
    print(f"EXECUTION        {r.get('execution_mode')}")

    s = r.get("session", {})
    print(f"\nSESSION          {s.get('status')}  phase={s.get('phase','-')}  "
          f"close={s.get('close_time')}")

    e = r.get("expiry", {})
    print(f"DTE              {e.get('days_to_expiry')}  ({e.get('note')})")

    ev = r.get("event_risk", {})
    print(f"EVENT RISK       {ev.get('state')}  next={ev.get('event')}  "
          f"in {ev.get('minutes_until', '-')}m")

    c = r.get("contract", {})
    if c:
        print(f"\nCONTRACT         {c.get('future')}")
        print(f"OPTION EXPIRY    {c.get('option_expiry')}")
        print(f"ATM              {c.get('atm')}  (future {c.get('future_ltp')})")

    p = r.get("previous_session", {})
    if p.get("status") == "OK":
        print(f"\nPREV OPEN        {p.get('prev_open')}")
        print(f"PREV HIGH        {p.get('prev_high')}")
        print(f"PREV LOW         {p.get('prev_low')}")
        print(f"PREV CLOSE       {p.get('prev_close')}")

    ext = r.get("external", {})
    if ext:
        print(f"\nEXTERNAL COMPOSITE  {ext.get('composite_regime')} ({ext.get('composite_pct')}%)")
        for k, v in (ext.get("primary") or {}).items():
            print(f"  {k:<10} {v.get('regime')}  ({v.get('chg_1')}%)")
        for k, v in (ext.get("cross_asset") or {}).items():
            print(f"  {k:<10} {v.get('regime')}  ({v.get('chg_1')}%)")

    cm = r.get("chain_metrics", {})
    if cm:
        print(f"\nPCR_OI           {cm.get('pcr_oi')}")
        print(f"MAX PAIN         {cm.get('max_pain')}")
        print(f"RESISTANCE       {cm.get('resistance')}")
        print(f"SUPPORT          {cm.get('support')}")

    print(f"\nMTF              {r.get('mtf_aggregate')}  (score={r.get('mtf_score')})")
    print(f"REGIME           {r.get('regime')} (conf={r.get('regime_confidence')})")

    print(f"\nOVERNIGHT BIAS   {r.get('overnight_bias')}")
    print(f"PLAN             {r.get('plan')}")
    print(f"NOTE             {r.get('note')}")
    print("=" * 100)


def format_header(product=None):
    """Return pre-session header string for a given product."""
    return f"MCX PRE-SESSION INTELLIGENCE \u2014 {product or 'MCX'}"


if __name__ == "__main__":
    print("mcx_presession module loaded OK")
