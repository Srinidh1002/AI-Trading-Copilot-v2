"""NATGASMINI fundamental engine — Section 5.12-5.18. Shadow-only."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_fundamental_models import make_observation, REASON_SOURCE_UNAVAILABLE
from mcx.mcx_fundamental_sources import (
    fetch_eia_natgas_storage, fetch_weather_hdd_cdd,
    fetch_lng_feedgas, fetch_natgas_production, fetch_pipeline_status,
)


def classify_storage_change(weekly_change_bcf):
    """Section 5.12 — injection vs withdrawal. Numeric preserved."""
    if weekly_change_bcf is None:
        return "DATA_UNAVAILABLE"
    if weekly_change_bcf > 0:
        return "INJECTION"
    if weekly_change_bcf < 0:
        return "WITHDRAWAL"
    return "FLAT"


def classify_storage_surprise(actual_change, consensus_change):
    """Section 5.13 — explicit sign-safe surprise classification.
    Example: expected +80, actual +60 → smaller injection.
             expected -100, actual -130 → larger withdrawal.
    """
    if consensus_change is None:
        return "CONSENSUS_UNAVAILABLE", None
    if actual_change is None:
        return "DATA_UNAVAILABLE", None
    try:
        delta = float(actual_change) - float(consensus_change)
    except Exception:
        return "DATA_UNAVAILABLE", None
    same_sign = (actual_change >= 0) == (consensus_change >= 0)
    if abs(delta) < 10:  # BCF tolerance for "in-line"
        return "INLINE", delta
    if consensus_change >= 0:
        # Injection expected
        if delta > 0:
            return "LARGER_INJECTION", delta
        return "SMALLER_INJECTION", delta
    else:
        # Withdrawal expected
        if abs(actual_change) > abs(consensus_change):
            return "LARGER_WITHDRAWAL", delta
        return "SMALLER_WITHDRAWAL", delta


def classify_weather_demand(forecast):
    """Section 5.14 — demand classification from HDD/CDD vs normal."""
    if not forecast:
        return "DATA_UNAVAILABLE"
    hdd = forecast.get("HDD", 0) or 0
    cdd = forecast.get("CDD", 0) or 0
    hdd_n = forecast.get("HDD_normal", 0) or 0
    cdd_n = forecast.get("CDD_normal", 0) or 0
    hdd_dev = hdd - hdd_n
    cdd_dev = cdd - cdd_n
    # Extreme
    if hdd_dev >= 10 or cdd_dev >= 10:
        return "EXTREME_WEATHER"
    if hdd_dev >= 2:
        return "HEATING_DEMAND"
    if cdd_dev >= 2:
        return "COOLING_DEMAND"
    if abs(hdd_dev) < 2 and abs(cdd_dev) < 2:
        return "NEUTRAL_WEATHER_DEMAND"
    return "NEUTRAL_WEATHER_DEMAND"


def build_natgas_observations(reference_week="2026-W36"):
    obs = {}

    eia = fetch_eia_natgas_storage(reference_week)
    if eia.status == "FIXTURE_LOADED":
        p = eia.payload
        weekly_change = p.get("weekly_change_bcf")
        consensus = p.get("consensus_change_bcf")
        storage_state = classify_storage_change(weekly_change)
        surprise_cls, surprise = classify_storage_surprise(weekly_change, consensus)
        obs["NATGAS_STORAGE"] = make_observation(
            product="NATGASMINI", driver_type="INVENTORY",
            metric_id="NATGAS_STORAGE",
            reference_period=reference_week,
            observation_time_iso=p["release_time_utc"],
            units="bcf", source="EIA",
            previous=p.get("previous_week_bcf"), consensus=consensus,
            actual=p.get("storage_current_bcf"),
            five_year_average=p.get("five_year_average_bcf"),
            freshness_policy="WEEKLY_EIA",
        )
        obs["NATGAS_STORAGE"]["weekly_change_bcf"] = weekly_change
        obs["NATGAS_STORAGE"]["injection_state"] = storage_state
        obs["NATGAS_STORAGE"]["surprise_class"] = surprise_cls
        obs["NATGAS_STORAGE"]["surprise_delta"] = surprise
    else:
        obs["EIA"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # Weather
    w = fetch_weather_hdd_cdd()
    if w.status == "FIXTURE_LOADED":
        p = w.payload
        forecast = p.get("forecast_1_3_day") or {}
        demand = classify_weather_demand(forecast)
        obs["WEATHER_DEMAND"] = make_observation(
            product="NATGASMINI", driver_type="WEATHER",
            metric_id="WEATHER_DEMAND",
            reference_period="2026-09-11",
            observation_time_iso=p["issue_time"],
            source="NOAA", freshness_policy="WEATHER",
            actual=forecast.get("HDD"),
            five_year_average=forecast.get("HDD_normal"),
            direction=demand,
        )
        obs["WEATHER_DEMAND"]["demand_class"] = demand
        obs["WEATHER_DEMAND"]["forecast_1_3"] = forecast
    else:
        obs["WEATHER"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # LNG
    lng = fetch_lng_feedgas()
    obs["LNG"] = {"status": "LNG_DEMAND_UNAVAILABLE",
                  "reason": lng.reason or "not configured"}

    # Production
    prod = fetch_natgas_production()
    if prod.status == "FIXTURE_LOADED":
        p = prod.payload
        if p.get("dry_gas_production_bcfd") is not None:
            obs["PRODUCTION"] = make_observation(
                product="NATGASMINI", driver_type="SUPPLY",
                metric_id="PRODUCTION",
                reference_period=p["period"],
                observation_time_iso="2026-09-11T00:00:00+00:00",
                source="EIA", freshness_policy="STRUCTURAL",
                actual=p["dry_gas_production_bcfd"],
            )
        else:
            obs["PRODUCTION"] = {"status": "PRODUCTION_DATA_UNAVAILABLE"}
    else:
        obs["PRODUCTION"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # Pipeline
    pl = fetch_pipeline_status()
    obs["PIPELINE"] = {"status": "PIPELINE_DATA_UNAVAILABLE"}

    return obs


def summarize_natgas(observations):
    def _get(mid):
        o = observations.get(mid, {})
        return o if isinstance(o, dict) and "actual" in o else None

    storage = _get("NATGAS_STORAGE")
    weather = _get("WEATHER_DEMAND")

    signals = []
    if storage and storage.get("weekly_change_bcf") is not None:
        chg = storage["weekly_change_bcf"]
        avg = storage.get("five_year_average")
        # Smaller-than-normal injection → bullish. Larger → bearish.
        signals.append("STORAGE_BULLISH" if chg < 60 else "STORAGE_BEARISH")

    if weather and weather.get("demand_class"):
        dc = weather["demand_class"]
        if dc == "HEATING_DEMAND":
            signals.append("WEATHER_BULLISH")  # heating demand up
        elif dc == "COOLING_DEMAND":
            signals.append("WEATHER_BULLISH")  # cooling demand up
        elif dc == "EXTREME_WEATHER":
            signals.append("WEATHER_BULLISH")
        else:
            signals.append("WEATHER_NEUTRAL")

    bull = sum(1 for s in signals if "BULLISH" in s)
    bear = sum(1 for s in signals if "BEARISH" in s)
    if bull > bear:
        state = "BULLISH"
    elif bear > bull:
        state = "BEARISH"
    elif bull == bear and bull > 0:
        state = "MIXED"
    else:
        state = "INCONCLUSIVE"

    expected = ["NATGAS_STORAGE", "WEATHER_DEMAND", "LNG", "PRODUCTION", "PIPELINE"]
    available = sum(1 for m in expected if _get(m) is not None
                    or observations.get(m, {}).get("status") is None)
    return {
        "product": "NATGASMINI",
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
    """Section 5 close-out P1: data-completeness category.
    NOT trade confidence, NOT win probability, NOT strategy score.
    """
    if ratio >= 0.80:
        return "HIGH"
    if ratio >= 0.60:
        return "MODERATE"
    if ratio >= 0.40:
        return "LOW"
    return "INSUFFICIENT"



if __name__ == "__main__":
    obs = build_natgas_observations()
    s = summarize_natgas(obs)
    print(f"NATGAS state: {s['fundamental_state']}")
    print(f"Completeness: {s['data_completeness']}")
    print("Sign-safe surprise tests:")
    for a, c, exp in [(60, 80, "SMALLER_INJECTION"), (100, 80, "LARGER_INJECTION"),
                      (-130, -100, "LARGER_WITHDRAWAL"), (-70, -100, "SMALLER_WITHDRAWAL")]:
        cls, _ = classify_storage_surprise(a, c)
        mark = "OK" if cls == exp else "MISMATCH"
        print(f"  actual={a} consensus={c} → {cls}  [{mark}]")
