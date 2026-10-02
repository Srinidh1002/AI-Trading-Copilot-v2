"""Pure, deterministic X4 futures research. No FYERS import, I/O or trade authority."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone

from services.x4.contracts_v1 import (
    X4BasisReferenceV1,
    X4ContractV1,
    X4FeatureV1,
    X4ResultV1,
    X4SampleV1,
    _aware,
)

# Adopt the existing MCX diagnostic thresholds; NOT trading-policy thresholds.
PRICE_CHANGE_THRESHOLD_PCT = 0.01
OI_CHANGE_THRESHOLD_PCT = 0.1


def _feature(
    feature_id: str,
    unit: str,
    dependencies: tuple[str, ...],
    value: float | None = None,
    *,
    blocker: str = "INSUFFICIENT_DATA",
    applicable: bool = True,
) -> X4FeatureV1:
    if not applicable:
        return X4FeatureV1(
            feature_id, "NOT_APPLICABLE", None, unit, "UNKNOWN", dependencies, (blocker,)
        )
    if value is None or not math.isfinite(value):
        return X4FeatureV1(
            feature_id, "UNAVAILABLE", None, unit, "UNKNOWN", dependencies, (blocker,)
        )
    direction = "UP" if value > 0 else ("DOWN" if value < 0 else "FLAT")
    return X4FeatureV1(feature_id, "AVAILABLE", float(value), unit, direction, dependencies)


def _pchange(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous <= 0:
        return None
    return (current - previous) * 100.0 / previous


def _oi(sample: X4SampleV1) -> float | None:
    return sample.open_interest if sample.oi_verified else None


def _volume(sample: X4SampleV1) -> float | None:
    return sample.volume if sample.volume_verified else None


def _acceleration(samples: tuple[X4SampleV1, ...]) -> float | None:
    if len(samples) < 3:
        return None
    a, b, c = samples[-3:]
    x, y, z = _oi(a), _oi(b), _oi(c)
    if x is None or y is None or z is None:
        return None
    dt1 = (b.observed_at - a.observed_at).total_seconds() / 3600.0
    dt2 = (c.observed_at - b.observed_at).total_seconds() / 3600.0
    if dt1 <= 0 or dt2 <= 0:
        return None
    rate1 = (y - x) / dt1
    rate2 = (z - y) / dt2
    return (rate2 - rate1) / ((dt1 + dt2) / 2.0)


def _candle_vwap_estimate(samples: tuple[X4SampleV1, ...]) -> float | None:
    """Typical-price candle approximation; never label as exchange/traded VWAP."""
    total_value = 0.0
    total_volume = 0.0
    for sample in samples:
        volume = _volume(sample)
        if volume is None or volume <= 0 or sample.high is None or sample.low is None:
            return None  # A missing bar cannot silently disappear from the session.
        typical = (sample.high + sample.low + sample.close) / 3.0
        total_value += typical * volume
        total_volume += volume
    return total_value / total_volume if total_volume > 0 else None


def _basis(
    contract: X4ContractV1,
    last: X4SampleV1,
    reference: X4BasisReferenceV1 | None,
    max_age_seconds: float,
    as_of: datetime,
) -> tuple[float | None, bool, str]:
    # Index levels are not commodity spot prices. MCX requires an independently
    # verified commodity-spot benchmark in the same physical price unit.
    is_index = contract.market in {"NIFTY", "SENSEX"}
    expected_type = "INDEX_SPOT" if is_index else "VERIFIED_COMMODITY_SPOT"
    if reference is None:
        return None, True, "BENCHMARK_UNAVAILABLE"
    if (
        reference.market != contract.market
        or reference.benchmark_type != expected_type
        or reference.price_unit != contract.price_unit
        or not reference.verified
    ):
        return None, False, "BENCHMARK_NOT_COMPARABLE_OR_UNVERIFIED"
    if (
        reference.observed_at > as_of
        or abs((reference.observed_at - last.observed_at).total_seconds()) > max_age_seconds
    ):
        return None, True, "BENCHMARK_STALE_OR_FUTURE_DATED"
    return last.close - reference.price, True, ""


def analyze_futures_v1(
    *,
    contract: X4ContractV1,
    samples: tuple[X4SampleV1, ...],
    as_of: datetime,
    max_age_seconds: float,
    basis_reference: X4BasisReferenceV1 | None = None,
) -> X4ResultV1:
    """Accept only ordered, completed, same-contract/same-session valid bars.

    The caller chooses the freshness budget for the input timeframe. Samples
    must be historical/as-of observations, never synthesized from a live LTP.
    """
    if (
        not _aware(as_of)
        or type(max_age_seconds) not in (int, float)
        or not math.isfinite(max_age_seconds)
        or max_age_seconds <= 0
    ):
        raise ValueError("Aware as_of and positive finite freshness budget required")
    if type(samples) is not tuple or not samples:
        raise ValueError("At least one immutable futures sample is required")
    if any(not isinstance(s, X4SampleV1) for s in samples):
        raise ValueError("Samples must use X4SampleV1")
    first = samples[0]
    if any(
        s.contract_id != contract.canonical_instrument_id
        or s.session_id != first.session_id
        or s.timeframe != first.timeframe
        or s.quality != "VALID"
        or not s.is_closed
        or s.observed_at > as_of
        for s in samples
    ):
        raise ValueError("Mixed/invalid contracts, sessions, timeframes or incomplete/future bars")
    if any(b.observed_at <= a.observed_at for a, b in zip(samples, samples[1:])):
        raise ValueError("Samples must be strictly increasing without duplicates")

    base = dict(
        market=contract.market,
        instrument_id=contract.canonical_instrument_id,
        session_id=first.session_id,
        timeframe=first.timeframe,
        as_of=as_of,
    )
    ist = as_of.astimezone(timezone(timedelta(hours=5, minutes=30)))
    expired = contract.expiry < ist.date()
    if contract.expiry == ist.date():
        # Existing F8 resolver conservatively excludes same-day MCX futures;
        # index futures are unavailable at/after the derivative close.
        expired = contract.market not in {"NIFTY", "SENSEX"} or ist.time() >= time(15, 30)
    if contract.metadata_status != "VERIFIED" or expired:
        return X4ResultV1(
            **base,
            features=(),
            positioning_state="UNKNOWN",
            status="UNAVAILABLE",
            blockers=("UNVERIFIED_OR_EXPIRED_CONTRACT",),
        )
    if (as_of - samples[-1].observed_at).total_seconds() > max_age_seconds:
        return X4ResultV1(
            **base,
            features=(),
            positioning_state="UNKNOWN",
            status="UNAVAILABLE",
            blockers=("STALE_FUTURES_SAMPLE",),
        )

    last = samples[-1]
    previous = samples[-2] if len(samples) >= 2 else None
    price_change = _pchange(previous.close, last.close) if previous else None
    prev_oi = _oi(previous) if previous else None
    last_oi = _oi(last)
    oi_change = _pchange(prev_oi, last_oi)
    oi_delta = (last_oi - prev_oi) if last_oi is not None and prev_oi is not None else None
    prev_volume = _volume(previous) if previous else None
    last_volume = _volume(last)
    vol_change = _pchange(prev_volume, last_volume)
    oi_acceleration = _acceleration(samples)
    vwap = _candle_vwap_estimate(samples)
    vwap_distance = (last.close - vwap) / vwap * 100.0 if vwap else None
    basis, basis_applicable, basis_blocker = _basis(
        contract, last, basis_reference, max_age_seconds, as_of
    )

    positioning = "UNKNOWN"
    if price_change is not None and oi_change is not None:
        if price_change > PRICE_CHANGE_THRESHOLD_PCT and oi_change > OI_CHANGE_THRESHOLD_PCT:
            positioning = "LONG_BUILDUP"
        elif price_change < -PRICE_CHANGE_THRESHOLD_PCT and oi_change > OI_CHANGE_THRESHOLD_PCT:
            positioning = "SHORT_BUILDUP"
        elif price_change > PRICE_CHANGE_THRESHOLD_PCT and oi_change < -OI_CHANGE_THRESHOLD_PCT:
            positioning = "SHORT_COVERING"
        elif price_change < -PRICE_CHANGE_THRESHOLD_PCT and oi_change < -OI_CHANGE_THRESHOLD_PCT:
            positioning = "LONG_UNWINDING"
        else:
            positioning = "FLAT"

    dependencies = (
        contract.canonical_instrument_id,
        first.session_id,
        first.timeframe,
        *(dict.fromkeys(s.source_id for s in samples)),
    )
    features = (
        _feature("FUTURES_PRICE_CHANGE_PCT", "PERCENT", dependencies, price_change),
        _feature(
            "FUTURES_OI_DELTA",
            "OI_PROVIDER_REPORTED_UNIT",
            dependencies,
            oi_delta,
            blocker="VERIFIED_OI_REQUIRED",
        ),
        _feature(
            "FUTURES_OI_CHANGE_PCT",
            "PERCENT",
            dependencies,
            oi_change,
            blocker="VERIFIED_OI_REQUIRED",
        ),
        _feature(
            "FUTURES_OI_ACCELERATION",
            "OI_PROVIDER_UNIT_PER_HOUR_SQUARED",
            dependencies,
            oi_acceleration,
            blocker="THREE_VERIFIED_OI_SAMPLES_REQUIRED",
        ),
        _feature(
            "FUTURES_VOLUME_CHANGE_PCT",
            "PERCENT",
            dependencies,
            vol_change,
            blocker="VERIFIED_POSITIVE_VOLUME_REQUIRED",
        ),
        _feature(
            "FUTURES_CANDLE_VWAP_ESTIMATE",
            contract.price_unit,
            dependencies,
            vwap,
            blocker="COMPLETE_VERIFIED_VOLUME_AND_OHLC_REQUIRED",
        ),
        _feature(
            "FUTURES_VWAP_ESTIMATE_DISTANCE_PCT",
            "PERCENT",
            dependencies,
            vwap_distance,
            blocker="CANDLE_VWAP_ESTIMATE_REQUIRED",
        ),
        _feature(
            "FUTURES_BASIS",
            contract.price_unit,
            dependencies,
            basis,
            blocker=basis_blocker,
            applicable=basis_applicable,
        ),
    )
    missing = tuple(f.feature_id for f in features if f.status == "UNAVAILABLE")
    status = "AVAILABLE" if not missing else "PARTIAL"
    return X4ResultV1(
        **base, features=features, positioning_state=positioning, status=status, blockers=missing
    )
