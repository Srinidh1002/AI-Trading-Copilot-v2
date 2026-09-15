"""GOLDM fundamental engine — Section 5.19-5.23. Shadow-only.
References Section-4 macro state; does NOT duplicate CPI parsing.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_fundamental_models import make_observation, REASON_SOURCE_UNAVAILABLE
from mcx.mcx_fundamental_sources import (
    fetch_real_yields, fetch_dxy, fetch_usdinr,
    fetch_gold_etf_flows, fetch_central_bank_gold, fetch_physical_gold_demand,
)


def classify_real_yields(current, previous):
    if current is None:
        return "DATA_UNAVAILABLE"
    if previous is None:
        return "REAL_YIELDS_STABLE"
    if current > previous:
        return "REAL_YIELDS_RISING"
    if current < previous:
        return "REAL_YIELDS_FALLING"
    return "REAL_YIELDS_STABLE"


def classify_central_bank(purchases, sales):
    """Slow-moving structural classification."""
    if purchases is None and sales is None:
        return "DATA_UNAVAILABLE"
    if purchases is not None and purchases > 0 and (sales is None or sales == 0):
        return "STRUCTURAL_SUPPORT"
    if sales is not None and sales > 0 and (purchases is None or purchases == 0):
        return "STRUCTURAL_PRESSURE"
    if purchases and sales:
        return "MIXED"
    return "DATA_UNAVAILABLE"


def build_gold_observations():
    obs = {}

    # Real yields
    ry = fetch_real_yields()
    if ry.status == "FIXTURE_LOADED":
        p = ry.payload
        state = classify_real_yields(p.get("us_10y_real_yield_pct"), p.get("previous_real_pct"))
        obs["REAL_YIELDS"] = make_observation(
            product="GOLDM", driver_type="YIELD",
            metric_id="REAL_YIELDS",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            units="percent", source="Treasury",
            previous=p.get("previous_real_pct"),
            actual=p.get("us_10y_real_yield_pct"),
            freshness_policy="DAILY_FLOW",
            direction=state,
        )
        obs["REAL_YIELDS"]["state"] = state
    else:
        obs["REAL_YIELDS"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # DXY
    dx = fetch_dxy()
    if dx.status == "FIXTURE_LOADED":
        p = dx.payload
        obs["DXY"] = make_observation(
            product="GOLDM", driver_type="FX",
            metric_id="DXY",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            source="yfinance",
            previous=p.get("previous_dxy"), actual=p.get("dxy"),
            freshness_policy="FAST_MARKET",
        )
    else:
        obs["DXY"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # USDINR
    ux = fetch_usdinr()
    if ux.status == "FIXTURE_LOADED":
        p = ux.payload
        obs["USDINR"] = make_observation(
            product="GOLDM", driver_type="FX",
            metric_id="USDINR",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            source="yfinance",
            previous=p.get("previous_usdinr"), actual=p.get("usdinr"),
            freshness_policy="FAST_MARKET",
        )

    # ETF
    etf = fetch_gold_etf_flows()
    if etf.status == "FIXTURE_LOADED" and etf.payload.get("holdings_tonnes") is not None:
        p = etf.payload
        obs["ETF_FLOWS"] = make_observation(
            product="GOLDM", driver_type="FLOW",
            metric_id="ETF_FLOWS",
            reference_period=p["period"],
            observation_time_iso="2026-09-11T00:00:00+00:00",
            units="tonnes", source="ETF",
            actual=p.get("holdings_tonnes"),
            freshness_policy="DAILY_FLOW",
        )
    else:
        obs["ETF_FLOWS"] = {"status": "ETF_FLOW_DATA_UNAVAILABLE"}

    # Central bank
    cb = fetch_central_bank_gold()
    if cb.status == "FIXTURE_LOADED" and cb.payload.get("purchases_tonnes") is not None:
        p = cb.payload
        state = classify_central_bank(p.get("purchases_tonnes"), p.get("sales_tonnes"))
        obs["CENTRAL_BANKS"] = make_observation(
            product="GOLDM", driver_type="FLOW",
            metric_id="CENTRAL_BANKS",
            reference_period=p["period"],
            observation_time_iso="2026-09-11T00:00:00+00:00",
            units="tonnes", source="IMF",
            actual=p.get("purchases_tonnes"),
            freshness_policy="MONTHLY_CB",
            direction=state,
        )
        obs["CENTRAL_BANKS"]["state"] = state
    else:
        obs["CENTRAL_BANKS"] = {"status": "CENTRAL_BANK_DATA_UNAVAILABLE"}

    # Physical demand
    ph = fetch_physical_gold_demand()
    obs["PHYSICAL_DEMAND"] = {"status": "PHYSICAL_DEMAND_UNAVAILABLE"}

    # Reference Section-4 macro (no duplication)
    try:
        from mcx.mcx_macro_engine import MacroEngine
        from datetime import datetime, timezone
        me = MacroEngine()
        rpt = me.shadow_report_for("GOLDM", datetime.now(timezone.utc))
        obs["MACRO_REF"] = {"status": "OK", "state": rpt.get("state"),
                            "next_event_type": rpt.get("next_event_type"),
                            "reference_only": True}
    except Exception as e:
        obs["MACRO_REF"] = {"status": REASON_SOURCE_UNAVAILABLE, "reason": str(e)[:60]}

    return obs


def summarize_gold(observations):
    def _get(mid):
        o = observations.get(mid, {})
        return o if isinstance(o, dict) and "actual" in o else None

    signals = []
    ry = _get("REAL_YIELDS")
    if ry and ry.get("state"):
        if ry["state"] == "REAL_YIELDS_RISING":
            signals.append("RY_BEARISH_GOLD")
        elif ry["state"] == "REAL_YIELDS_FALLING":
            signals.append("RY_BULLISH_GOLD")
    dxy = _get("DXY")
    if dxy and dxy.get("actual") and dxy.get("previous"):
        if dxy["actual"] > dxy["previous"]:
            signals.append("DXY_BEARISH_GOLD")
        elif dxy["actual"] < dxy["previous"]:
            signals.append("DXY_BULLISH_GOLD")
    etf = _get("ETF_FLOWS")
    if etf and etf.get("actual") is not None:
        signals.append("ETF_INFLOW" if etf["actual"] > 0 else "ETF_OUTFLOW")
    cb = _get("CENTRAL_BANKS")
    if cb and cb.get("state") == "STRUCTURAL_SUPPORT":
        signals.append("CB_BULLISH_GOLD")

    bull = sum(1 for s in signals if "BULLISH" in s or "INFLOW" in s)
    bear = sum(1 for s in signals if "BEARISH" in s or "OUTFLOW" in s)
    if bull > bear:
        state = "BULLISH"
    elif bear > bull:
        state = "BEARISH"
    elif bull == bear and bull > 0:
        state = "MIXED"
    else:
        state = "INCONCLUSIVE"

    expected = ["REAL_YIELDS", "DXY", "USDINR", "ETF_FLOWS", "CENTRAL_BANKS", "PHYSICAL_DEMAND"]
    available = sum(1 for m in expected if _get(m) is not None)
    return {
        "product": "GOLDM",
        "signals": signals,
        "fundamental_state": state,
        "raw_fundamental_state": state,
        "data_completeness": {"expected": len(expected), "available": available,
                             "ratio": round(available / len(expected), 3)},
        "evidence_authority": _evidence_authority(round(available / len(expected), 3)),
        "shadow_only": True,
        "trade_influence": False,
    }


def _evidence_authority(ratio):
    """Section 5 close-out P1: data-completeness category."""
    if ratio >= 0.80:
        return "HIGH"
    if ratio >= 0.60:
        return "MODERATE"
    if ratio >= 0.40:
        return "LOW"
    return "INSUFFICIENT"



if __name__ == "__main__":
    obs = build_gold_observations()
    s = summarize_gold(obs)
    print(f"GOLD state: {s['fundamental_state']}")
    print(f"Signals: {s['signals']}")
    print(f"Completeness: {s['data_completeness']}")
