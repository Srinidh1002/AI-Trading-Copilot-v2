"""X6-B3 descriptive ATM volatility, comparable IV history and expected move.

Research only. Every IV is inferred from verified option premiums using X6-B2;
neither an independently observed FYERS IV nor a directional/trade signal.
Historical summaries require different point-in-time sessions, the same expiry
and the same ATM strike. Expected move is an approximate one-sigma scale, not a
probabilistic promise, stop level or executable trade range.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime

from services.x5.contracts_v1 import X5ChainCaptureV1, canonical_sha256
from services.x6.contracts_v1 import (
    MODEL_BY_MARKET,
    PRICE_UNITS,
    X6VolatilityCaptureV1,
    _aware,
    _disabled_authority,
    _sha,
    _text,
)
from services.x6.iv_greeks_v1 import X6IVGreeksResultV1, analyze_iv_greeks_v1

_NAMES_UNITS = {
    "ATM_IV": "DECIMAL_ANNUAL_VOLATILITY",
    "ATM_IV_SKEW": "VOLATILITY_PERCENTAGE_POINTS_PUT_MINUS_CALL",
    "EXPECTED_MOVE_1SIGMA": "UNDERLYING_PRICE_UNIT",
    "IV_CHANGE": "VOLATILITY_PERCENTAGE_POINTS",
    "IV_PERCENTILE": "PERCENTILE_0_TO_100",
}
_GROUPS = {
    "ATM_IV": "ATM_IV_DEPENDENCY",
    "ATM_IV_SKEW": "ATM_IV_DEPENDENCY",
    "EXPECTED_MOVE_1SIGMA": "ATM_IV_DEPENDENCY",
    "IV_CHANGE": "ATM_IV_HISTORY_DEPENDENCY",
    "IV_PERCENTILE": "ATM_IV_HISTORY_DEPENDENCY",
}


def _num(x: object, *, positive: bool = False, signed: bool = False) -> bool:
    return (
        type(x) in (int, float)
        and math.isfinite(x)
        and (not positive or x > 0)
        and (signed or x >= 0)
    )


def _messages(x: object) -> bool:
    return type(x) is tuple and all(_text(v) for v in x)


@dataclass(frozen=True, slots=True)
class X6VolatilityFeatureV1:
    name: str
    status: str
    value: float | None
    unit: str
    dependency_group: str
    source_record_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_VOLATILITY_FEATURE_V1"

    def __post_init__(self) -> None:
        if (
            self.name not in _NAMES_UNITS
            or self.unit != _NAMES_UNITS[self.name]
            or self.dependency_group != _GROUPS[self.name]
        ):
            raise ValueError("Unregistered or reclassified volatility feature")
        if self.status not in {"AVAILABLE", "RETROSPECTIVE", "UNAVAILABLE"}:
            raise ValueError("Invalid feature status")
        if (
            not _messages(self.source_record_ids)
            or not _messages(self.blockers)
            or not _messages(self.warnings)
        ):
            raise ValueError("Feature evidence and diagnostics must be immutable")
        if self.status == "UNAVAILABLE":
            if self.value is not None or not self.blockers:
                raise ValueError("Unavailable feature cannot retain a value")
        elif (
            not _num(self.value, signed=self.name in ("ATM_IV_SKEW", "IV_CHANGE")) or self.blockers
        ):
            raise ValueError("Available feature needs a finite value without blockers")
        if self.value is not None:
            if self.name == "ATM_IV" and not 0 < self.value <= 5:
                raise ValueError("Invalid annualized IV")
            if self.name == "IV_PERCENTILE" and not 0 <= self.value <= 100:
                raise ValueError("Invalid percentile")
            if self.name == "EXPECTED_MOVE_1SIGMA" and self.value <= 0:
                raise ValueError("Expected move must be positive")
        _disabled_authority(self, "X6_VOLATILITY_FEATURE_V1")


@dataclass(frozen=True, slots=True)
class X6ATMHistoryPointV1:
    market: str
    model: str
    reference_unit: str
    option_expiry: date
    atm_strike: float
    as_of: datetime
    session_id: str
    capture_id: str
    atm_iv_decimal: float
    source_record_ids: tuple[str, str]
    source_x6_capture_sha256: str
    source_iv_greeks_sha256: str
    point_in_time_verified: bool = True
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_ATM_HISTORY_POINT_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MODEL_BY_MARKET
            or self.model != MODEL_BY_MARKET[self.market]
            or self.reference_unit != PRICE_UNITS[self.market]
        ):
            raise ValueError("Invalid historical market/model/units")
        if (
            not isinstance(self.option_expiry, date)
            or isinstance(self.option_expiry, datetime)
            or not _num(self.atm_strike, positive=True)
            or not _aware(self.as_of)
            or self.as_of.date() > self.option_expiry
        ):
            raise ValueError("Invalid historical expiry/strike/timestamp")
        if not (
            _text(self.session_id)
            and _text(self.capture_id)
            and _messages(self.source_record_ids)
            and len(self.source_record_ids) == 2
            and self.source_record_ids[0] != self.source_record_ids[1]
            and _sha(self.source_x6_capture_sha256)
            and _sha(self.source_iv_greeks_sha256)
        ):
            raise ValueError("Historical summary must carry exact source identifiers")
        if not _num(self.atm_iv_decimal, positive=True) or self.atm_iv_decimal > 5:
            raise ValueError("Invalid historical annualized IV")
        if self.point_in_time_verified is not True:
            raise ValueError("A retrospective result cannot become a comparable historical sample")
        _disabled_authority(self, "X6_ATM_HISTORY_POINT_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class X6VolatilityRegimeResultV1:
    market: str
    model: str
    capture_id: str
    as_of: datetime
    option_expiry: date
    atm_strike: float | None
    status: str
    regime: str
    features: tuple[X6VolatilityFeatureV1, ...]
    comparable_history_count: int
    history_minimum: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_x6_capture_sha256: str
    source_x5_capture_sha256: str
    source_iv_greeks_sha256: str
    source_history_sha256: tuple[str, ...]
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_VOLATILITY_REGIME_RESULT_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MODEL_BY_MARKET
            or self.model != MODEL_BY_MARKET[self.market]
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or not isinstance(self.option_expiry, date)
            or isinstance(self.option_expiry, datetime)
        ):
            raise ValueError("Invalid regime identity")
        if self.atm_strike is not None and not _num(self.atm_strike, positive=True):
            raise ValueError("Invalid ATM strike")
        if self.status not in {"AVAILABLE", "PARTIAL", "RETROSPECTIVE", "UNAVAILABLE"}:
            raise ValueError("Invalid regime status")
        if self.regime not in {"LOW", "MIDDLE", "HIGH", "UNKNOWN"}:
            raise ValueError("Invalid descriptive regime")
        if (
            type(self.features) is not tuple
            or len(self.features) != len(_NAMES_UNITS)
            or tuple(f.name for f in self.features) != tuple(_NAMES_UNITS)
        ):
            raise ValueError("Exactly five registered features are required")
        if (
            type(self.comparable_history_count) is not int
            or type(self.history_minimum) is not int
            or (self.comparable_history_count < 0 or self.history_minimum < 2)
        ):
            raise ValueError("Invalid history count")
        if (
            not _messages(self.blockers)
            or not _messages(self.warnings)
            or type(self.source_history_sha256) is not tuple
            or any(not _sha(x) for x in self.source_history_sha256)
            or any(
                not _sha(x)
                for x in (
                    self.source_x6_capture_sha256,
                    self.source_x5_capture_sha256,
                    self.source_iv_greeks_sha256,
                )
            )
        ):
            raise ValueError("Invalid provenance")
        if self.comparable_history_count > len(self.source_history_sha256):
            raise ValueError("Comparable history cannot exceed total source history")
        if self.regime != "UNKNOWN" and (
            self.features[4].status != "AVAILABLE"
            or self.comparable_history_count < self.history_minimum
        ):
            raise ValueError("Regime classification requires sufficient point-in-time history")
        current_statuses = tuple(f.status for f in self.features[:3])
        historical_statuses = tuple(f.status for f in self.features[3:])
        if self.status == "UNAVAILABLE" and (
            not self.blockers
            or current_statuses != ("UNAVAILABLE",) * 3
            or historical_statuses != ("UNAVAILABLE",) * 2
        ):
            raise ValueError("Unavailable result cannot retain derived values")
        if self.status == "RETROSPECTIVE" and (
            current_statuses != ("RETROSPECTIVE",) * 3
            or historical_statuses != ("UNAVAILABLE",) * 2
            or self.regime != "UNKNOWN"
        ):
            raise ValueError("Retrospective inputs cannot create historical comparisons")
        if self.status == "AVAILABLE" and (
            current_statuses != ("AVAILABLE",) * 3
            or historical_statuses != ("AVAILABLE",) * 2
            or self.regime == "UNKNOWN"
        ):
            raise ValueError("Fully available result requires all five valid features")
        if self.status == "PARTIAL" and (
            current_statuses != ("AVAILABLE",) * 3 or historical_statuses == ("AVAILABLE",) * 2
        ):
            raise ValueError("Partial result needs current evidence and missing history")
        _disabled_authority(self, "X6_VOLATILITY_REGIME_RESULT_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def _feature(
    name: str,
    value: float | None,
    status: str,
    ids: tuple[str, ...],
    reason: str,
    warnings: tuple[str, ...] = (),
) -> X6VolatilityFeatureV1:
    if value is None:
        return X6VolatilityFeatureV1(
            name, "UNAVAILABLE", None, _NAMES_UNITS[name], _GROUPS[name], ids, (reason,), warnings
        )
    return X6VolatilityFeatureV1(
        name, status, value, _NAMES_UNITS[name], _GROUPS[name], ids, (), warnings
    )


def _atm_pair(capture: X6VolatilityCaptureV1, result: X6IVGreeksResultV1):
    """Nearest *captured* strike only; never skip to a farther complete pair."""
    if not capture.observations or not capture.context.reference_verified:
        return None, None, "REFERENCE_OR_CAPTURE_UNAVAILABLE"
    reference = capture.context.reference_price
    strike = min(
        {row.strike for row in capture.observations}, key=lambda x: (abs(x - reference), x)
    )
    sides = {r.option_type: r for r in result.rows if r.strike == strike}
    call, put = sides.get("CE"), sides.get("PE")
    if call is None or put is None:
        return strike, None, "NEAREST_STRIKE_PAIR_INCOMPLETE"
    if call.status == "UNAVAILABLE" or put.status == "UNAVAILABLE":
        return strike, None, "ATM_IV_PAIR_UNAVAILABLE"
    status = "AVAILABLE" if call.status == put.status == "AVAILABLE" else "RETROSPECTIVE"
    return strike, (call, put, status), ""


def _verify_binding(
    capture: X6VolatilityCaptureV1, source_x5: X5ChainCaptureV1, iv_greeks: X6IVGreeksResultV1
) -> None:
    if not isinstance(iv_greeks, X6IVGreeksResultV1):
        raise TypeError("Actual X6-B2 result is required")
    if (
        iv_greeks.market != capture.context.market
        or iv_greeks.model != capture.context.model
        or iv_greeks.capture_id != capture.capture_id
        or iv_greeks.as_of != capture.context.as_of
        or iv_greeks.source_x6_capture_sha256 != capture.sha256()
        or iv_greeks.source_x5_capture_sha256 != source_x5.sha256()
    ):
        raise ValueError("X6-B2 result is not bound to the supplied X5/X6 capture")
    # Independent recalculation also verifies stored validation, row values and metadata.
    recalculated = analyze_iv_greeks_v1(capture=capture, source_x5=source_x5)
    if recalculated.sha256() != iv_greeks.sha256():
        raise ValueError("Stored IV/Greeks result differs from deterministic source replay")


def make_x6_atm_history_point_v1(
    *, capture: X6VolatilityCaptureV1, source_x5: X5ChainCaptureV1, iv_greeks: X6IVGreeksResultV1
) -> X6ATMHistoryPointV1:
    """Create one point-in-time historical sample from a replay-checked B2 result."""
    _verify_binding(capture, source_x5, iv_greeks)
    strike, pair, reason = _atm_pair(capture, iv_greeks)
    if pair is None or pair[2] != "AVAILABLE" or not capture.point_in_time_verified:
        raise ValueError(reason or "HISTORY_REQUIRES_POINT_IN_TIME_ATM_PAIR")
    call, put, _ = pair
    return X6ATMHistoryPointV1(
        market=capture.context.market,
        model=capture.context.model,
        reference_unit=capture.context.reference_unit,
        option_expiry=capture.context.option_expiry,
        atm_strike=strike,
        as_of=capture.context.as_of,
        session_id=capture.session_id,
        capture_id=capture.capture_id,
        atm_iv_decimal=(call.implied_volatility_decimal + put.implied_volatility_decimal) / 2,
        source_record_ids=(call.source_record_id, put.source_record_id),
        source_x6_capture_sha256=capture.sha256(),
        source_iv_greeks_sha256=iv_greeks.sha256(),
    )


def analyze_volatility_regime_v1(
    *,
    capture: X6VolatilityCaptureV1,
    source_x5: X5ChainCaptureV1,
    iv_greeks: X6IVGreeksResultV1,
    history: tuple[X6ATMHistoryPointV1, ...] = (),
    history_minimum: int = 20,
) -> X6VolatilityRegimeResultV1:
    """Captured-window ATM summary; strictly comparable historical percentile.

    History must be frozen PIT observations in strictly increasing timestamp order
    with unique session/capture identities. Expiry/ATM-strike mismatches are
    excluded (and disclosed), not silently blended. Percentile uses rank of
    current ATM IV relative to prior observations: 100 * count(prior <= now)/N.
    """
    _verify_binding(capture, source_x5, iv_greeks)
    if type(history) is not tuple or any(not isinstance(x, X6ATMHistoryPointV1) for x in history):
        raise TypeError("History must be a tuple of frozen X6 ATM points")
    if type(history_minimum) is not int or not 2 <= history_minimum <= 10_000:
        raise ValueError("History minimum must be between 2 and 10000")
    prior_time = None
    seen_sessions: set[str] = set()
    seen_ids: set[str] = set()
    for point in history:
        if (
            point.market != capture.context.market
            or point.model != capture.context.model
            or point.reference_unit != capture.context.reference_unit
        ):
            raise ValueError("Mixed markets, models or units in X6 historical comparison")
        if (
            point.as_of >= capture.context.as_of
            or (prior_time is not None and point.as_of <= prior_time)
            or point.session_id in seen_sessions
            or point.capture_id in seen_ids
            or point.source_x6_capture_sha256 == capture.sha256()
        ):
            raise ValueError("History must be chronological, distinct and strictly prior")
        seen_sessions.add(point.session_id)
        seen_ids.add(point.capture_id)
        prior_time = point.as_of
    strike, pair, reason = _atm_pair(capture, iv_greeks)
    origin = () if pair is None else (pair[0].source_record_id, pair[1].source_record_id)
    core_status = pair[2] if pair is not None else "UNAVAILABLE"
    iv = (
        (pair[0].implied_volatility_decimal + pair[1].implied_volatility_decimal) / 2
        if pair
        else None
    )
    skew = (
        (pair[1].implied_volatility_decimal - pair[0].implied_volatility_decimal) * 100
        if pair
        else None
    )
    t = capture.context.time_to_expiry_years()
    move = (
        capture.context.reference_price * iv * math.sqrt(t)
        if iv is not None and t is not None and t > 0
        else None
    )
    features = [
        _feature("ATM_IV", iv, core_status, origin, reason or "ATM_IV_UNAVAILABLE"),
        _feature("ATM_IV_SKEW", skew, core_status, origin, reason or "ATM_IV_SKEW_UNAVAILABLE"),
        _feature(
            "EXPECTED_MOVE_1SIGMA",
            move,
            core_status,
            origin,
            reason or "EXPECTED_MOVE_INPUT_UNAVAILABLE",
            ("APPROXIMATE_ONE_SIGMA_NOT_PRICE_BOUNDS",),
        ),
    ]
    compatible = tuple(
        p
        for p in history
        if p.option_expiry == capture.context.option_expiry
        and strike is not None
        and p.atm_strike == strike
    )
    excluded = len(history) - len(compatible)
    warnings: list[str] = ["MODEL_IMPLIED_NOT_PROVIDER_VERIFIED_IV", "CAPTURED_STRIKE_WINDOW_ONLY"]
    if excluded:
        warnings.append("EXCLUDED_NONCOMPARABLE_EXPIRY_OR_ATM_STRIKE")
    if iv_greeks.status == "PARTIAL":
        warnings.append("PARTIAL_IV_STRIKE_COVERAGE")
    historical_ids = tuple(p.sha256() for p in compatible)
    if core_status != "AVAILABLE":
        change, percentile = None, None
        history_reason = "CURRENT_POINT_IN_TIME_ATM_IV_UNAVAILABLE"
    elif not compatible:
        change, percentile = None, None
        history_reason = "NO_COMPARABLE_POINT_IN_TIME_HISTORY"
    else:
        change = (iv - compatible[-1].atm_iv_decimal) * 100
        percentile = (
            100 * sum(p.atm_iv_decimal <= iv for p in compatible) / len(compatible)
            if len(compatible) >= history_minimum
            else None
        )
        history_reason = "INSUFFICIENT_DISTINCT_HISTORY_SESSIONS"
    features.append(
        _feature(
            "IV_CHANGE",
            change,
            "AVAILABLE",
            historical_ids[-1:] + origin,
            "NO_COMPARABLE_PREVIOUS_ATM_IV" if change is None else "",
        )
    )
    features.append(
        _feature(
            "IV_PERCENTILE",
            percentile,
            "AVAILABLE",
            historical_ids + origin,
            history_reason if percentile is None else "",
        )
    )
    regime = (
        "UNKNOWN"
        if percentile is None
        else ("LOW" if percentile <= 25 else "HIGH" if percentile >= 75 else "MIDDLE")
    )
    if core_status == "UNAVAILABLE":
        status = "UNAVAILABLE"
        blockers = (reason,)
    elif core_status == "RETROSPECTIVE":
        status = "RETROSPECTIVE"
        blockers = ()
        warnings.append("RETROSPECTIVE_CURRENT_CAPTURE_NO_HISTORICAL_COMPARISON")
    elif percentile is None or change is None:
        status = "PARTIAL"
        blockers = ()
        warnings.append("HISTORY_METRICS_UNAVAILABLE")
    else:
        status = "AVAILABLE"
        blockers = ()
    return X6VolatilityRegimeResultV1(
        market=capture.context.market,
        model=capture.context.model,
        capture_id=capture.capture_id,
        as_of=capture.context.as_of,
        option_expiry=capture.context.option_expiry,
        atm_strike=strike,
        status=status,
        regime=regime,
        features=tuple(features),
        comparable_history_count=len(compatible),
        history_minimum=history_minimum,
        blockers=blockers,
        warnings=tuple(warnings),
        source_x6_capture_sha256=capture.sha256(),
        source_x5_capture_sha256=source_x5.sha256(),
        source_iv_greeks_sha256=iv_greeks.sha256(),
        source_history_sha256=tuple(p.sha256() for p in history),
    )
