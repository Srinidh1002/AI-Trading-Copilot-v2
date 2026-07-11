"""Option-chain open-interest analysis for support, resistance, and sentiment."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypedDict


class OptionAnalysis(TypedDict):
    """Normalised option-chain analysis returned to callers."""

    pcr: float
    support: int
    resistance: int
    max_pain: int
    call_oi: int
    put_oi: int
    call_change_oi: int
    put_change_oi: int
    score: int
    confidence: int
    reasons: list[str]


@dataclass(frozen=True)
class _StrikeInterest:
    """Open-interest values for one option strike."""

    strike: int
    call_oi: int
    put_oi: int
    call_change_oi: int
    put_change_oi: int


def _clamp(value: float) -> int:
    """Convert a score to a bounded percentage."""

    return max(0, min(100, round(value)))


def _number(value: object, *, allow_negative: bool = False) -> int:
    """Safely convert NSE numeric fields, including comma-formatted strings."""

    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(number) or (number < 0 and not allow_negative):
        return 0
    return round(number)


def _records(option_chain: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Extract option records from raw or NSE-wrapped option-chain responses."""

    containers: list[object] = [option_chain]
    for key in ("records", "filtered"):
        nested = option_chain.get(key)
        if isinstance(nested, Mapping):
            containers.append(nested)

    for container in containers:
        if not isinstance(container, Mapping):
            continue
        data = container.get("data")
        if isinstance(data, list):
            return (record for record in data if isinstance(record, Mapping))
    return ()


def _leg(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return an option leg while accepting upper- and lower-case keys."""

    value = record.get(key) or record.get(key.lower())
    return value if isinstance(value, Mapping) else {}


def _field(leg: Mapping[str, Any], *names: str, allow_negative: bool = False) -> int:
    """Read the first available numeric field from an option leg."""

    for name in names:
        if name in leg:
            return _number(leg[name], allow_negative=allow_negative)
    return 0


def _parse_strikes(option_chain: Mapping[str, Any]) -> list[_StrikeInterest]:
    """Normalise valid option-chain rows into per-strike open interest."""

    parsed: list[_StrikeInterest] = []
    for record in _records(option_chain):
        strike = _field(record, "strikePrice", "strike", "strike_price")
        if strike <= 0:
            continue
        call = _leg(record, "CE")
        put = _leg(record, "PE")
        parsed.append(
            _StrikeInterest(
                strike=strike,
                call_oi=_field(call, "openInterest", "oi"),
                put_oi=_field(put, "openInterest", "oi"),
                call_change_oi=_field(
                    call, "changeinOpenInterest", "change_oi", allow_negative=True
                ),
                put_change_oi=_field(
                    put, "changeinOpenInterest", "change_oi", allow_negative=True
                ),
            )
        )
    return parsed


def _max_pain(strikes: list[_StrikeInterest]) -> int:
    """Find the settlement strike with the lowest aggregate option payout."""

    if not strikes:
        return 0

    def payout(settlement: int) -> int:
        return sum(
            item.call_oi * max(0, settlement - item.strike)
            + item.put_oi * max(0, item.strike - settlement)
            for item in strikes
        )

    return min((item.strike for item in strikes), key=payout)


def _neutral_analysis(reason: str) -> OptionAnalysis:
    """Return a safe, serialisable response for unusable chain data."""

    return {
        "pcr": 0.0,
        "support": 0,
        "resistance": 0,
        "max_pain": 0,
        "call_oi": 0,
        "put_oi": 0,
        "call_change_oi": 0,
        "put_change_oi": 0,
        "score": 50,
        "confidence": 0,
        "reasons": [reason],
    }


def analyse_options(option_chain: Mapping[str, Any]) -> OptionAnalysis:
    """Analyse an NSE-style option-chain dictionary.

    Support and resistance are respectively the strikes with the largest put
    and call open interest.  The maximum writing strikes use the largest
    positive change in open interest.  ``score`` is a 0--100 sentiment score,
    with 50 neutral; PCR and fresh writing determine its direction.

    Args:
        option_chain: Raw option-chain data, either with a top-level ``data``
            list or NSE's ``records.data`` / ``filtered.data`` wrapper.

    Returns:
        Calculated OI metrics, levels, a sentiment score, confidence, and
        human-readable reasons.

    Raises:
        TypeError: If ``option_chain`` is not a dictionary-like mapping.
    """

    if not isinstance(option_chain, Mapping):
        raise TypeError("option_chain must be a dictionary containing option data")

    strikes = _parse_strikes(option_chain)
    if not strikes:
        return _neutral_analysis("No valid option-chain strikes are available.")

    call_oi = sum(item.call_oi for item in strikes)
    put_oi = sum(item.put_oi for item in strikes)
    call_change_oi = sum(item.call_change_oi for item in strikes)
    put_change_oi = sum(item.put_change_oi for item in strikes)
    pcr = round(put_oi / call_oi, 4) if call_oi else 0.0

    resistance = max(strikes, key=lambda item: item.call_oi).strike
    support = max(strikes, key=lambda item: item.put_oi).strike
    max_call_writing = max(strikes, key=lambda item: item.call_change_oi)
    max_put_writing = max(strikes, key=lambda item: item.put_change_oi)

    score_direction = 0
    reasons: list[str] = []
    if call_oi == 0:
        reasons.append("Call open interest is unavailable; PCR is set to 0.0.")
    elif pcr > 1:
        score_direction += 10
        reasons.append(f"PCR is bullish at {pcr:.2f}.")
    elif pcr < 0.8:
        score_direction -= 10
        reasons.append(f"PCR is bearish at {pcr:.2f}.")
    else:
        reasons.append(f"PCR is neutral at {pcr:.2f}.")

    if put_change_oi > call_change_oi:
        score_direction += 15
        reasons.append("Fresh put writing exceeds fresh call writing.")
    elif call_change_oi > put_change_oi:
        score_direction -= 15
        reasons.append("Fresh call writing exceeds fresh put writing.")
    else:
        reasons.append("Call and put open-interest changes are balanced.")

    if max_call_writing.call_change_oi > 0:
        reasons.append(
            f"Maximum call writing is at {max_call_writing.strike}."
        )
    if max_put_writing.put_change_oi > 0:
        reasons.append(f"Maximum put writing is at {max_put_writing.strike}.")
    reasons.append(f"Support is concentrated at {support} put OI.")
    reasons.append(f"Resistance is concentrated at {resistance} call OI.")

    coverage = min(1.0, len(strikes) / 10)
    evidence = 1.0 if call_oi > 0 and put_oi > 0 else 0.5
    confidence = _clamp((40 + abs(score_direction) * 2) * coverage * evidence)

    return {
        "pcr": pcr,
        "support": support,
        "resistance": resistance,
        "max_pain": _max_pain(strikes),
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_change_oi": call_change_oi,
        "put_change_oi": put_change_oi,
        "score": _clamp(50 + score_direction),
        "confidence": confidence,
        "reasons": reasons,
    }
