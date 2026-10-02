"""Pure captured-window option analytics; deterministic evidence without voting or orders.

Consumes validated X5 captures. Mirrors established canonical arithmetic for PCR,
max pain, OI concentration/buildup, levels and IV skew, but does not import the
legacy universe or production policy/aggregation modules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import isfinite

from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import (
    MARKET_EXCHANGES,
    X5ChainCaptureV1,
    X5ChainValidationV1,
    canonical_sha256,
)

_GROUPS = {
    "PCR_OI": "OPTION_OI_POSITIONING",
    "PCR_VOLUME": "OPTION_FLOW_VOLUME",
    "MAX_PAIN": "OPTION_OI_POSITIONING",
    "OI_CONCENTRATION": "OPTION_OI_POSITIONING",
    "OI_BUILDUP": "OPTION_OI_POSITIONING",
    "OI_SUPPORT_RESISTANCE": "OPTION_OI_POSITIONING",
    "IV_SKEW": "OPTION_VOLATILITY",
    "QUOTE_SPREAD": "OPTION_QUOTE_LIQUIDITY",
    "GREEKS": "OPTION_GREEKS_SHAPE",
}
_UNITS = {
    "PCR_OI": "RATIO",
    "PCR_VOLUME": "RATIO",
    "MAX_PAIN": "UNDERLYING_PRICE_UNIT",
    "OI_CONCENTRATION": "RATIO",
    "OI_BUILDUP": "RATIO",
    "OI_SUPPORT_RESISTANCE": "BPS",
    "IV_SKEW": "PERCENTAGE_POINTS",
    "QUOTE_SPREAD": "BPS",
    "GREEKS": "MEAN_ABS_DELTA",
}


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _finite(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True, slots=True)
class X5ResearchMetricV1:
    metric_name: str
    status: str
    value: float | None
    unit: str
    dependency_group: str
    supporting_strikes: tuple[float, ...]
    detail: tuple[tuple[str, float], ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_RESEARCH_METRIC_V1"

    def __post_init__(self) -> None:
        if self.metric_name not in METRICS or self.unit != _UNITS[self.metric_name]:
            raise ValueError("Invalid metric identity/unit")
        if self.dependency_group != _GROUPS[self.metric_name]:
            raise ValueError("Metric dependency group mismatch")
        if self.status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError("Invalid metric status")
        if self.status == "AVAILABLE" and not _finite(self.value):
            raise ValueError("Available metric requires finite numeric value")
        if self.status == "UNAVAILABLE" and (self.value is not None or not self.blockers):
            raise ValueError("Unavailable metric requires a blocker and no value")
        if (
            type(self.supporting_strikes) is not tuple
            or any(not _finite(s) or s <= 0 for s in self.supporting_strikes)
            or tuple(sorted(set(self.supporting_strikes))) != self.supporting_strikes
        ):
            raise ValueError("Invalid supporting strikes")
        if (
            type(self.detail) is not tuple
            or len({k for k, _ in self.detail}) != len(self.detail)
            or any(not _text(k) or not _finite(v) for k, v in self.detail)
        ):
            raise ValueError("Invalid detail")
        if any(not _text(x) for x in self.blockers + self.warnings):
            raise ValueError("Invalid metric diagnostic")
        if self.scope != "CAPTURED_STRIKE_WINDOW" or self.schema_version != "X5_RESEARCH_METRIC_V1":
            raise ValueError("Metric cannot claim exchange-wide scope")
        if (
            self.independent_vote is not False
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Metric has no trading or independent voting authority")


@dataclass(frozen=True, slots=True)
class X5AnalyticsResultV1:
    market: str
    expiry: date
    capture_id: str
    as_of: datetime
    status: str
    metrics: tuple[X5ResearchMetricV1, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_capture_sha256: str
    source_validation_sha256: str
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_ANALYTICS_RESULT_V1"

    def __post_init__(self) -> None:
        if self.market not in MARKET_EXCHANGES or not _text(self.capture_id):
            raise ValueError("Invalid analytics identity")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("Analytics timestamp must be aware")
        if self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("Invalid analytics status")
        if type(self.metrics) is not tuple or tuple(m.metric_name for m in self.metrics) != METRICS:
            raise ValueError("Exactly one metric per canonical feature is required")
        if not all(_text(x) for x in (self.source_capture_sha256, self.source_validation_sha256)):
            raise ValueError("Provenance hashes are required")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.schema_version != "X5_ANALYTICS_RESULT_V1"
        ):
            raise ValueError("Analytics scope/schema cannot change")
        if (
            self.independent_vote is not False
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Analytics cannot acquire trading authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def _metric(
    name: str,
    value: float | None,
    strikes: tuple[float, ...],
    *,
    detail: tuple[tuple[str, float], ...] = (),
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> X5ResearchMetricV1:
    return X5ResearchMetricV1(
        metric_name=name,
        status="AVAILABLE" if not blockers else "UNAVAILABLE",
        value=float(value) if not blockers and value is not None else None,
        unit=_UNITS[name],
        dependency_group=_GROUPS[name],
        supporting_strikes=strikes,
        detail=detail if not blockers else (),
        blockers=blockers,
        warnings=warnings,
    )


def _unavailable(name: str, reason: str) -> X5ResearchMetricV1:
    return _metric(name, None, (), blockers=(reason,))


def _pair_rows(capture: X5ChainCaptureV1):
    ce = {float(x.strike): x for x in capture.observations if x.option_type == "CE"}
    pe = {float(x.strike): x for x in capture.observations if x.option_type == "PE"}
    return [(s, ce[s], pe[s]) for s in sorted(ce.keys() & pe.keys())]


def _calculate(name: str, capture: X5ChainCaptureV1, pairs) -> X5ResearchMetricV1:
    strikes = tuple(s for s, _, _ in pairs)
    spot = capture.underlying_value
    if name in {"PCR_OI", "PCR_VOLUME"}:
        field = "open_interest" if name == "PCR_OI" else "volume"
        call = sum(getattr(c, field) for _, c, _ in pairs)
        put = sum(getattr(p, field) for _, _, p in pairs)
        if call <= 0:
            return _unavailable(name, "ZERO_CALL_DENOMINATOR")
        return _metric(
            name,
            put / call,
            strikes,
            detail=(("put_total", float(put)), ("call_total", float(call))),
        )
    if name == "MAX_PAIN":
        total_oi = sum(c.open_interest + p.open_interest for _, c, p in pairs)
        if total_oi <= 0:
            return _unavailable(name, "ZERO_TOTAL_OI")
        payouts = [
            (
                s,
                sum(
                    max(s - k, 0) * c.open_interest + max(k - s, 0) * p.open_interest
                    for k, c, p in pairs
                ),
            )
            for s in strikes
        ]
        minimum = min(v for _, v in payouts)
        ties = tuple(s for s, pain in payouts if pain == minimum)
        selected = min(ties, key=lambda s: (abs(s - spot), s))
        return _metric(
            name,
            selected,
            strikes,
            detail=(
                ("minimum_pain", float(minimum)),
                ("tied_strike_count", float(len(ties))),
                ("signed_distance_bps", (selected - spot) / spot * 10000),
            ),
        )
    if name == "OI_CONCENTRATION":
        values = [(s, c.open_interest + p.open_interest) for s, c, p in pairs]
        total = sum(v for _, v in values)
        if total <= 0:
            return _unavailable(name, "ZERO_TOTAL_OI")
        max_value = max(v for _, v in values)
        top = min(s for s, v in values if v == max_value)
        return _metric(
            name,
            max_value / total,
            strikes,
            detail=(
                ("top_strike", top),
                ("top_oi", float(max_value)),
                ("total_oi", float(total)),
            ),
        )
    if name == "OI_BUILDUP":
        # Baselines must denote the same comparison window; different per-row IDs
        # may identify different sources but cannot establish that comparability.
        baseline_ids = {x.oi_change_baseline_id for x in capture.observations}
        if len(baseline_ids) != 1:
            return _unavailable(name, "OI_CHANGE_BASELINE_NOT_COMPARABLE")
        call = sum(c.change_in_open_interest for _, c, _ in pairs)
        put = sum(p.change_in_open_interest for _, _, p in pairs)
        gross = abs(call) + abs(put)
        net = put - call
        return _metric(
            name,
            net / gross if gross else 0.0,
            strikes,
            detail=(
                ("put_change_total", float(put)),
                ("call_change_total", float(call)),
                ("net_change_imbalance", float(net)),
                ("gross_absolute_change", float(gross)),
            ),
            warnings=("BOTH_SIDES_UNWINDING",) if call < 0 and put < 0 else (),
        )
    if name == "OI_SUPPORT_RESISTANCE":
        support = [(s, p.open_interest) for s, _, p in pairs if s <= spot]
        resistance = [(s, c.open_interest) for s, c, _ in pairs if s >= spot]
        if not support or not resistance:
            return _unavailable(name, "BOTH_LEVEL_SIDES_REQUIRED")
        s, s_oi = min(support, key=lambda x: (-x[1], abs(x[0] - spot), x[0]))
        r, r_oi = min(resistance, key=lambda x: (-x[1], abs(x[0] - spot), x[0]))
        return _metric(
            name,
            (r - s) / spot * 10000,
            strikes,
            detail=(
                ("support_strike", s),
                ("support_put_oi", float(s_oi)),
                ("resistance_strike", r),
                ("resistance_call_oi", float(r_oi)),
            ),
        )
    if name == "IV_SKEW":
        multiplier = 100.0 if pairs[0][1].iv_unit == "DECIMAL" else 1.0
        call = sum(c.implied_volatility for _, c, _ in pairs) / len(pairs) * multiplier
        put = sum(p.implied_volatility for _, _, p in pairs) / len(pairs) * multiplier
        return _metric(
            name,
            put - call,
            strikes,
            detail=(("avg_call_iv_percent", call), ("avg_put_iv_percent", put)),
        )
    if name == "QUOTE_SPREAD":
        values = []
        for _, c, p in pairs:
            for x in (c, p):
                middle = (x.bid_price + x.ask_price) / 2
                if middle <= 0:
                    return _unavailable(name, "ZERO_QUOTE_MIDPOINT")
                values.append((x.ask_price - x.bid_price) / middle * 10000)
        return _metric(
            name,
            sum(values) / len(values),
            strikes,
            detail=(("max_spread_bps", max(values)), ("quote_count", float(len(values)))),
        )
    if name == "GREEKS":
        call_delta = sum(c.delta for _, c, _ in pairs) / len(pairs)
        put_delta = sum(p.delta for _, _, p in pairs) / len(pairs)
        mean_abs = sum(abs(x.delta) for _, c, p in pairs for x in (c, p)) / (2 * len(pairs))
        return _metric(
            name,
            mean_abs,
            strikes,
            detail=(
                ("avg_call_delta", call_delta),
                ("avg_put_delta", put_delta),
                ("avg_gamma", sum(x.gamma for _, c, p in pairs for x in (c, p)) / (2 * len(pairs))),
                ("avg_theta", sum(x.theta for _, c, p in pairs for x in (c, p)) / (2 * len(pairs))),
                ("avg_vega", sum(x.vega for _, c, p in pairs for x in (c, p)) / (2 * len(pairs))),
            ),
        )
    raise AssertionError(f"Unexpected metric: {name}")


def analyze_x5_chain_v1(
    *, capture: X5ChainCaptureV1, max_age_seconds: float
) -> X5AnalyticsResultV1:
    """Compute only validation-approved captured-window metrics, never a vote."""
    if not isinstance(capture, X5ChainCaptureV1):
        raise ValueError("X5ChainCaptureV1 is required")
    validation: X5ChainValidationV1 = validate_x5_chain_v1(capture, max_age_seconds=max_age_seconds)
    ready = dict(validation.readiness)
    pairs = _pair_rows(capture)
    results = tuple(
        _calculate(name, capture, pairs)
        if ready[name] == "AVAILABLE"
        else _unavailable(name, "X5_VALIDATION_NOT_READY")
        for name in METRICS
    )
    available = sum(x.status == "AVAILABLE" for x in results)
    status = (
        "UNAVAILABLE" if not available else "AVAILABLE" if available == len(METRICS) else "PARTIAL"
    )
    return X5AnalyticsResultV1(
        market=capture.contract.market,
        expiry=capture.contract.expiry,
        capture_id=capture.capture_id,
        as_of=capture.as_of,
        status=status,
        metrics=results,
        blockers=validation.blockers,
        warnings=validation.warnings,
        source_capture_sha256=capture.sha256(),
        source_validation_sha256=validation.sha256(),
    )
