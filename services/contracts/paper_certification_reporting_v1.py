"""Immutable daily, weekly and monthly PAPER certification reports."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import ClassVar


_MARKETS = {"NIFTY", "SENSEX"}
_ACTIONS = {"CALL", "PUT", "WAIT"}
_REPORT_STATUSES = {"RECONCILED"}
_INCIDENT_TYPES = {"DATA_PROVIDER", "LIFECYCLE", "SYSTEM"}
_SEVERITIES = {"INFO", "WARNING", "ERROR", "CRITICAL"}
_DUPLICATE_TYPES = {
    "PROVIDER_CALL",
    "PREDICTION",
    "ENTRY",
    "EXIT",
    "OTHER",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _date(value: object, name: str) -> date:
    if type(value) is not date:
        raise TypeError(name)
    return value


def _count(value: object, name: str) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(name)
    return value


def _number(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise ValueError(name)
    return float(value)


def _positive(value: object, name: str) -> float:
    result = _number(value, name)
    if result <= 0.0:
        raise ValueError(name)
    return result


def _optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    return _number(value, name)


def _optional_percent(value: object, name: str) -> float | None:
    result = _optional_number(value, name)
    if result is not None and not 0.0 <= result <= 100.0:
        raise ValueError(name)
    return result


def _messages(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _pairs(
    value: object,
    name: str,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    result: list[tuple[str, float]] = []
    seen: set[str] = set()
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError(name)
        key = _text(item[0], name)
        if key in seen:
            raise ValueError(f"duplicate {name} key")
        seen.add(key)
        result.append((key, _number(item[1], name)))
    return tuple(sorted(result))


def _distribution(
    value: object,
    name: str,
) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    result: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError(name)
        key = _text(item[0], name)
        if key in seen:
            raise ValueError(f"duplicate {name} key")
        seen.add(key)
        result.append((key, _count(item[1], name)))
    return tuple(sorted(result))


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class PredictionCertificationAnalyticsContextV1:
    prediction_id: str
    confidence_band: str = "UNAVAILABLE"
    regime: str = "UNAVAILABLE"
    time_of_day: str = "UNAVAILABLE"
    contract_quality: str = "UNAVAILABLE"
    spread_quality: str = "UNAVAILABLE"
    liquidity_quality: str = "UNAVAILABLE"
    engine_contributions: tuple[tuple[str, float], ...] = ()
    pillar_contributions: tuple[tuple[str, float], ...] = ()
    schema_version: str = "prediction_certification_analytics_context.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prediction_id",
            _text(self.prediction_id, "prediction_id"),
        )
        for name in (
            "confidence_band",
            "regime",
            "time_of_day",
            "contract_quality",
            "spread_quality",
            "liquidity_quality",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name).upper(),
            )
        object.__setattr__(
            self,
            "engine_contributions",
            _pairs(
                self.engine_contributions,
                "engine_contributions",
            ),
        )
        object.__setattr__(
            self,
            "pillar_contributions",
            _pairs(
                self.pillar_contributions,
                "pillar_contributions",
            ),
        )
        if (
            self.schema_version
            != "prediction_certification_analytics_context.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["engine_contributions"] = dict(
            self.engine_contributions
        )
        result["pillar_contributions"] = dict(
            self.pillar_contributions
        )
        return result


@dataclass(frozen=True, slots=True)
class CertificationIncidentV1:
    incident_id: str
    occurred_at: datetime
    incident_type: str
    severity: str
    code: str
    resolved: bool
    market: str | None = None
    details: tuple[str, ...] = ()
    schema_version: str = "certification_incident.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "incident_id",
            _text(self.incident_id, "incident_id"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _aware(self.occurred_at, "occurred_at"),
        )
        incident_type = _text(
            self.incident_type,
            "incident_type",
        ).upper()
        severity = _text(self.severity, "severity").upper()
        if incident_type not in _INCIDENT_TYPES:
            raise ValueError("incident_type")
        if severity not in _SEVERITIES:
            raise ValueError("severity")
        object.__setattr__(
            self,
            "incident_type",
            incident_type,
        )
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "code", _text(self.code, "code").upper())
        if type(self.resolved) is not bool:
            raise TypeError("resolved")
        if self.market is not None:
            market = _text(self.market, "market").upper()
            if market not in _MARKETS:
                raise ValueError("market")
            object.__setattr__(self, "market", market)
        object.__setattr__(
            self,
            "details",
            _messages(self.details, "details"),
        )
        if self.schema_version != "certification_incident.v1":
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["occurred_at"] = self.occurred_at.isoformat()
        value["details"] = list(self.details)
        return value


@dataclass(frozen=True, slots=True)
class CertificationDuplicateAttemptV1:
    attempt_id: str
    occurred_at: datetime
    duplicate_type: str
    blocked: bool
    reference_id: str
    market: str | None = None
    reason_codes: tuple[str, ...] = ()
    schema_version: str = "certification_duplicate_attempt.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attempt_id",
            _text(self.attempt_id, "attempt_id"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _aware(self.occurred_at, "occurred_at"),
        )
        duplicate_type = _text(
            self.duplicate_type,
            "duplicate_type",
        ).upper()
        if duplicate_type not in _DUPLICATE_TYPES:
            raise ValueError("duplicate_type")
        object.__setattr__(
            self,
            "duplicate_type",
            duplicate_type,
        )
        if type(self.blocked) is not bool:
            raise TypeError("blocked")
        if self.blocked is not True:
            raise ValueError(
                "certification duplicate attempts must be blocked"
            )
        object.__setattr__(
            self,
            "reference_id",
            _text(self.reference_id, "reference_id"),
        )
        if self.market is not None:
            market = _text(self.market, "market").upper()
            if market not in _MARKETS:
                raise ValueError("market")
            object.__setattr__(self, "market", market)
        object.__setattr__(
            self,
            "reason_codes",
            _messages(self.reason_codes, "reason_codes"),
        )
        if (
            self.schema_version
            != "certification_duplicate_attempt.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["occurred_at"] = self.occurred_at.isoformat()
        value["reason_codes"] = list(self.reason_codes)
        return value


@dataclass(frozen=True, slots=True)
class CertificationAuditItemV1:
    prediction_id: str
    status: str
    reason_codes: tuple[str, ...]
    schema_version: str = "certification_audit_item.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prediction_id",
            _text(self.prediction_id, "prediction_id"),
        )
        object.__setattr__(
            self,
            "status",
            _text(self.status, "status").upper(),
        )
        reasons = _messages(self.reason_codes, "reason_codes")
        if not reasons:
            raise ValueError("reason_codes")
        object.__setattr__(self, "reason_codes", reasons)
        if self.schema_version != "certification_audit_item.v1":
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["reason_codes"] = list(self.reason_codes)
        return value


@dataclass(frozen=True, slots=True)
class CertificationPredictionFactV1:
    prediction_id: str
    parent_cycle_id: str
    market: str
    action: str
    direction: str
    confidence: float
    confidence_band: str
    regime: str
    time_of_day: str
    contract_quality: str
    spread_quality: str
    liquidity_quality: str
    parent_selected: bool
    parent_decision: str
    counting_status: str
    officially_counted: bool
    lifecycle_status: str
    outcome: str
    reconciliation_status: str
    entry_occurred: bool
    closed_position: bool
    success: bool | None
    gross_pnl: float
    net_pnl: float
    policy_version: str
    engine_contributions: tuple[tuple[str, float], ...] = ()
    pillar_contributions: tuple[tuple[str, float], ...] = ()
    schema_version: str = "certification_prediction_fact.v1"

    def __post_init__(self) -> None:
        for name in ("prediction_id", "parent_cycle_id", "policy_version"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        for name in (
            "direction",
            "confidence_band",
            "regime",
            "time_of_day",
            "contract_quality",
            "spread_quality",
            "liquidity_quality",
            "parent_decision",
            "counting_status",
            "lifecycle_status",
            "outcome",
            "reconciliation_status",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name).upper(),
            )
        market = _text(self.market, "market").upper()
        action = _text(self.action, "action").upper()
        if market not in _MARKETS:
            raise ValueError("market")
        if action not in _ACTIONS:
            raise ValueError("action")
        object.__setattr__(self, "market", market)
        object.__setattr__(self, "action", action)
        confidence = _number(self.confidence, "confidence")
        if not 0.0 <= confidence <= 100.0:
            raise ValueError("confidence")
        object.__setattr__(self, "confidence", confidence)
        for name in (
            "parent_selected",
            "officially_counted",
            "entry_occurred",
            "closed_position",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("success")
        object.__setattr__(
            self,
            "gross_pnl",
            _number(self.gross_pnl, "gross_pnl"),
        )
        object.__setattr__(
            self,
            "net_pnl",
            _number(self.net_pnl, "net_pnl"),
        )
        object.__setattr__(
            self,
            "engine_contributions",
            _pairs(
                self.engine_contributions,
                "engine_contributions",
            ),
        )
        object.__setattr__(
            self,
            "pillar_contributions",
            _pairs(
                self.pillar_contributions,
                "pillar_contributions",
            ),
        )
        if (
            self.officially_counted
            and (
                self.lifecycle_status != "RESOLVED"
                or self.reconciliation_status != "RECONCILED"
            )
        ):
            raise ValueError("official counting coherence")
        if self.schema_version != "certification_prediction_fact.v1":
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["engine_contributions"] = dict(
            self.engine_contributions
        )
        value["pillar_contributions"] = dict(
            self.pillar_contributions
        )
        return value


@dataclass(frozen=True, slots=True)
class CertificationPerformanceSliceV1:
    key: str
    prediction_count: int
    resolved_count: int
    success_count: int
    failure_count: int
    closed_trade_count: int
    gross_pnl: float
    net_pnl: float
    expectancy: float | None
    reliability_percent: float | None
    schema_version: str = "certification_performance_slice.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "key"))
        for name in (
            "prediction_count",
            "resolved_count",
            "success_count",
            "failure_count",
            "closed_trade_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )
        if (
            self.success_count + self.failure_count
            != self.resolved_count
        ):
            raise ValueError("resolved count reconciliation")
        object.__setattr__(
            self,
            "gross_pnl",
            _number(self.gross_pnl, "gross_pnl"),
        )
        object.__setattr__(
            self,
            "net_pnl",
            _number(self.net_pnl, "net_pnl"),
        )
        expectancy = _optional_number(self.expectancy, "expectancy")
        expected_expectancy = (
            self.net_pnl / self.closed_trade_count
            if self.closed_trade_count
            else None
        )
        if (
            expectancy is None
        ) != (
            expected_expectancy is None
        ) or (
            expectancy is not None
            and not math.isclose(
                expectancy,
                expected_expectancy,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("expectancy mismatch")
        reliability = _optional_percent(
            self.reliability_percent,
            "reliability_percent",
        )
        expected_reliability = (
            self.success_count / self.resolved_count * 100.0
            if self.resolved_count
            else None
        )
        if (
            reliability is None
        ) != (
            expected_reliability is None
        ) or (
            reliability is not None
            and not math.isclose(
                reliability,
                expected_reliability,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("reliability mismatch")
        object.__setattr__(self, "expectancy", expectancy)
        object.__setattr__(
            self,
            "reliability_percent",
            reliability,
        )
        if (
            self.schema_version
            != "certification_performance_slice.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CertificationConfidenceCalibrationV1:
    confidence_band: str
    prediction_count: int
    average_confidence_percent: float
    observed_success_percent: float
    calibration_error_points: float
    schema_version: str = "certification_confidence_calibration.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confidence_band",
            _text(self.confidence_band, "confidence_band").upper(),
        )
        object.__setattr__(
            self,
            "prediction_count",
            _count(self.prediction_count, "prediction_count"),
        )
        if self.prediction_count == 0:
            raise ValueError("prediction_count")
        average = _optional_percent(
            self.average_confidence_percent,
            "average_confidence_percent",
        )
        observed = _optional_percent(
            self.observed_success_percent,
            "observed_success_percent",
        )
        error = _number(
            self.calibration_error_points,
            "calibration_error_points",
        )
        if average is None or observed is None or error < 0.0:
            raise ValueError("confidence calibration")
        expected = abs(average - observed)
        if not math.isclose(error, expected, abs_tol=1e-9):
            raise ValueError("calibration error mismatch")
        object.__setattr__(
            self,
            "average_confidence_percent",
            average,
        )
        object.__setattr__(
            self,
            "observed_success_percent",
            observed,
        )
        object.__setattr__(
            self,
            "calibration_error_points",
            error,
        )
        if (
            self.schema_version
            != "certification_confidence_calibration.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CertificationCapitalPointV1:
    session_date: date
    starting_capital: float
    ending_capital: float
    net_pnl: float
    schema_version: str = "certification_capital_point.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "session_date",
            _date(self.session_date, "session_date"),
        )
        start = _positive(self.starting_capital, "starting_capital")
        end = _positive(self.ending_capital, "ending_capital")
        pnl = _number(self.net_pnl, "net_pnl")
        if not math.isclose(start + pnl, end, abs_tol=1e-9):
            raise ValueError("capital point reconciliation")
        object.__setattr__(self, "starting_capital", start)
        object.__setattr__(self, "ending_capital", end)
        object.__setattr__(self, "net_pnl", pnl)
        if self.schema_version != "certification_capital_point.v1":
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["session_date"] = self.session_date.isoformat()
        return value


@dataclass(frozen=True, slots=True)
class CertificationDrawdownPeriodV1:
    started_on: date
    trough_on: date
    recovered_on: date | None
    peak_capital: float
    trough_capital: float
    drawdown_amount: float
    drawdown_percent: float
    schema_version: str = "certification_drawdown_period.v1"

    def __post_init__(self) -> None:
        start = _date(self.started_on, "started_on")
        trough = _date(self.trough_on, "trough_on")
        recovered = (
            None
            if self.recovered_on is None
            else _date(self.recovered_on, "recovered_on")
        )
        if trough < start or (
            recovered is not None and recovered < trough
        ):
            raise ValueError("drawdown date ordering")
        peak = _positive(self.peak_capital, "peak_capital")
        trough_capital = _positive(
            self.trough_capital,
            "trough_capital",
        )
        amount = _number(self.drawdown_amount, "drawdown_amount")
        percent = _number(
            self.drawdown_percent,
            "drawdown_percent",
        )
        expected_amount = peak - trough_capital
        expected_percent = expected_amount / peak * 100.0
        if (
            amount < 0.0
            or percent < 0.0
            or not math.isclose(
                amount,
                expected_amount,
                abs_tol=1e-9,
            )
            or not math.isclose(
                percent,
                expected_percent,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("drawdown reconciliation")
        object.__setattr__(self, "peak_capital", peak)
        object.__setattr__(
            self,
            "trough_capital",
            trough_capital,
        )
        object.__setattr__(
            self,
            "drawdown_amount",
            amount,
        )
        object.__setattr__(
            self,
            "drawdown_percent",
            percent,
        )
        if self.schema_version != "certification_drawdown_period.v1":
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        for name in ("started_on", "trough_on", "recovered_on"):
            item = getattr(self, name)
            value[name] = (
                item.isoformat()
                if item is not None
                else None
            )
        return value


@dataclass(frozen=True, slots=True)
class PaperCertificationDailyReportV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "paper_certification_daily_report.v1"
    )

    report_id: str
    session_date: date
    generated_at: datetime
    starting_capital: float
    ending_capital: float
    source_prediction_count: int
    official_prediction_count: int
    completed_outcome_count: int
    pending_outcome_count: int
    excluded_prediction_count: int
    no_trade_cycle_count: int
    entry_count: int
    closed_position_count: int
    win_count: int
    loss_count: int
    break_even_count: int
    gross_pnl: float
    net_pnl: float
    market_distribution: tuple[tuple[str, int], ...]
    action_distribution: tuple[tuple[str, int], ...]
    selected_market_distribution: tuple[tuple[str, int], ...]
    outcome_distribution: tuple[tuple[str, int], ...]
    reconciliation_distribution: tuple[tuple[str, int], ...]
    incident_distribution: tuple[tuple[str, int], ...]
    duplicate_distribution: tuple[tuple[str, int], ...]
    prediction_facts: tuple[CertificationPredictionFactV1, ...]
    excluded_audit: tuple[CertificationAuditItemV1, ...]
    unresolved_audit: tuple[CertificationAuditItemV1, ...]
    incidents: tuple[CertificationIncidentV1, ...]
    duplicate_attempts: tuple[CertificationDuplicateAttemptV1, ...]
    report_status: str = "RECONCILED"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "report_id",
            _text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self,
            "session_date",
            _date(self.session_date, "session_date"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )
        start = _positive(self.starting_capital, "starting_capital")
        end = _positive(self.ending_capital, "ending_capital")
        gross = _number(self.gross_pnl, "gross_pnl")
        net = _number(self.net_pnl, "net_pnl")
        if not math.isclose(start + net, end, abs_tol=1e-9):
            raise ValueError("daily capital reconciliation")
        object.__setattr__(self, "starting_capital", start)
        object.__setattr__(self, "ending_capital", end)
        object.__setattr__(self, "gross_pnl", gross)
        object.__setattr__(self, "net_pnl", net)

        for name in (
            "source_prediction_count",
            "official_prediction_count",
            "completed_outcome_count",
            "pending_outcome_count",
            "excluded_prediction_count",
            "no_trade_cycle_count",
            "entry_count",
            "closed_position_count",
            "win_count",
            "loss_count",
            "break_even_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )

        if (
            self.official_prediction_count
            + self.pending_outcome_count
            + self.excluded_prediction_count
            != self.source_prediction_count
        ):
            raise ValueError("daily prediction reconciliation")
        if (
            self.win_count
            + self.loss_count
            + self.break_even_count
            != self.closed_position_count
        ):
            raise ValueError("daily closed position reconciliation")

        for name in (
            "market_distribution",
            "action_distribution",
            "selected_market_distribution",
            "outcome_distribution",
            "reconciliation_distribution",
            "incident_distribution",
            "duplicate_distribution",
        ):
            object.__setattr__(
                self,
                name,
                _distribution(getattr(self, name), name),
            )

        typed_sequences = (
            (
                "prediction_facts",
                CertificationPredictionFactV1,
            ),
            ("excluded_audit", CertificationAuditItemV1),
            ("unresolved_audit", CertificationAuditItemV1),
            ("incidents", CertificationIncidentV1),
            (
                "duplicate_attempts",
                CertificationDuplicateAttemptV1,
            ),
        )
        for name, expected in typed_sequences:
            value = getattr(self, name)
            if type(value) is not tuple or any(
                type(item) is not expected
                for item in value
            ):
                raise TypeError(name)

        if len(self.prediction_facts) != self.source_prediction_count:
            raise ValueError("daily fact count mismatch")
        if sum(
            1
            for item in self.prediction_facts
            if item.officially_counted
        ) != self.official_prediction_count:
            raise ValueError("daily official count mismatch")
        if len(self.excluded_audit) != self.excluded_prediction_count:
            raise ValueError("daily excluded audit mismatch")
        if len(self.unresolved_audit) != self.pending_outcome_count:
            raise ValueError("daily unresolved audit mismatch")
        if sum(count for _, count in self.market_distribution) != (
            self.source_prediction_count
        ):
            raise ValueError("daily market distribution mismatch")
        if sum(count for _, count in self.action_distribution) != (
            self.source_prediction_count
        ):
            raise ValueError("daily action distribution mismatch")
        if sum(
            count for _, count in self.selected_market_distribution
        ) != sum(
            item.parent_selected for item in self.prediction_facts
        ):
            raise ValueError("daily selected-market distribution mismatch")
        if sum(count for _, count in self.outcome_distribution) != (
            self.source_prediction_count
        ):
            raise ValueError("daily outcome distribution mismatch")
        if sum(
            count for _, count in self.reconciliation_distribution
        ) != self.source_prediction_count:
            raise ValueError("daily reconciliation distribution mismatch")
        if self.completed_outcome_count != sum(
            item.lifecycle_status == "RESOLVED"
            for item in self.prediction_facts
        ):
            raise ValueError("daily completed outcome mismatch")
        if self.no_trade_cycle_count != len(
            {
                item.parent_cycle_id
                for item in self.prediction_facts
                if item.parent_decision == "NO_TRADE"
            }
        ):
            raise ValueError("daily no-trade cycle mismatch")
        if self.entry_count != sum(
            item.entry_occurred for item in self.prediction_facts
        ):
            raise ValueError("daily entry count mismatch")
        if self.closed_position_count != sum(
            item.closed_position for item in self.prediction_facts
        ):
            raise ValueError("daily closed position count mismatch")
        fact_gross = sum(
            item.gross_pnl
            for item in self.prediction_facts
            if item.closed_position
        )
        fact_net = sum(
            item.net_pnl
            for item in self.prediction_facts
            if item.closed_position
        )
        if not math.isclose(
            self.gross_pnl, fact_gross, abs_tol=1e-9
        ):
            raise ValueError("daily gross P&L mismatch")
        if not math.isclose(
            self.net_pnl, fact_net, abs_tol=1e-9
        ):
            raise ValueError("daily net P&L mismatch")
        if sum(count for _, count in self.incident_distribution) != len(
            self.incidents
        ):
            raise ValueError("daily incident distribution mismatch")
        if sum(count for _, count in self.duplicate_distribution) != len(
            self.duplicate_attempts
        ):
            raise ValueError("daily duplicate distribution mismatch")

        status = _text(
            self.report_status,
            "report_status",
        ).upper()
        if status not in _REPORT_STATUSES:
            raise ValueError("report_status")
        object.__setattr__(self, "report_status", status)

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only daily certification report")

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "session_date": self.session_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "starting_capital": self.starting_capital,
            "ending_capital": self.ending_capital,
            "source_prediction_count": self.source_prediction_count,
            "official_prediction_count": self.official_prediction_count,
            "completed_outcome_count": self.completed_outcome_count,
            "pending_outcome_count": self.pending_outcome_count,
            "excluded_prediction_count": self.excluded_prediction_count,
            "no_trade_cycle_count": self.no_trade_cycle_count,
            "entry_count": self.entry_count,
            "closed_position_count": self.closed_position_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "break_even_count": self.break_even_count,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "market_distribution": dict(self.market_distribution),
            "action_distribution": dict(self.action_distribution),
            "selected_market_distribution": dict(
                self.selected_market_distribution
            ),
            "outcome_distribution": dict(
                self.outcome_distribution
            ),
            "reconciliation_distribution": dict(
                self.reconciliation_distribution
            ),
            "incident_distribution": dict(
                self.incident_distribution
            ),
            "duplicate_distribution": dict(
                self.duplicate_distribution
            ),
            "prediction_facts": [
                item.to_dict()
                for item in self.prediction_facts
            ],
            "excluded_audit": [
                item.to_dict()
                for item in self.excluded_audit
            ],
            "unresolved_audit": [
                item.to_dict()
                for item in self.unresolved_audit
            ],
            "incidents": [
                item.to_dict()
                for item in self.incidents
            ],
            "duplicate_attempts": [
                item.to_dict()
                for item in self.duplicate_attempts
            ],
            "report_status": self.report_status,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "broker_order_submission": self.broker_order_submission,
            "read_only": self.read_only,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return _json(self.to_dict())

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperCertificationWeeklyReportV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "paper_certification_weekly_report.v1"
    )

    report_id: str
    week_started_on: date
    week_ended_on: date
    generated_at: datetime
    daily_report_ids: tuple[str, ...]
    starting_capital: float
    ending_capital: float
    net_pnl: float
    maximum_drawdown_amount: float
    maximum_drawdown_percent: float
    official_prediction_count: int
    closed_position_count: int
    expectancy: float | None
    reliability_percent: float | None
    market_performance: tuple[CertificationPerformanceSliceV1, ...]
    confidence_band_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    regime_performance: tuple[CertificationPerformanceSliceV1, ...]
    direction_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    time_of_day_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    contract_quality_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    spread_quality_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    liquidity_quality_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    rejected_signal_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    policy_version_performance: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    report_status: str = "RECONCILED"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "report_id",
            _text(self.report_id, "report_id"),
        )
        start_date = _date(
            self.week_started_on,
            "week_started_on",
        )
        end_date = _date(
            self.week_ended_on,
            "week_ended_on",
        )
        if start_date > end_date:
            raise ValueError("weekly date ordering")
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )
        if type(self.daily_report_ids) is not tuple:
            raise TypeError("daily_report_ids")
        ids = tuple(
            _text(item, "daily_report_ids")
            for item in self.daily_report_ids
        )
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("daily_report_ids")
        object.__setattr__(self, "daily_report_ids", ids)

        start = _positive(self.starting_capital, "starting_capital")
        end = _positive(self.ending_capital, "ending_capital")
        net = _number(self.net_pnl, "net_pnl")
        if not math.isclose(start + net, end, abs_tol=1e-9):
            raise ValueError("weekly capital reconciliation")
        object.__setattr__(self, "starting_capital", start)
        object.__setattr__(self, "ending_capital", end)
        object.__setattr__(self, "net_pnl", net)

        drawdown = _number(
            self.maximum_drawdown_amount,
            "maximum_drawdown_amount",
        )
        drawdown_percent = _number(
            self.maximum_drawdown_percent,
            "maximum_drawdown_percent",
        )
        if drawdown < 0.0 or drawdown_percent < 0.0:
            raise ValueError("maximum drawdown")
        object.__setattr__(
            self,
            "maximum_drawdown_amount",
            drawdown,
        )
        object.__setattr__(
            self,
            "maximum_drawdown_percent",
            drawdown_percent,
        )

        for name in (
            "official_prediction_count",
            "closed_position_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )

        expectancy = _optional_number(self.expectancy, "expectancy")
        expected_expectancy = (
            net / self.closed_position_count
            if self.closed_position_count
            else None
        )
        if (
            expectancy is None
        ) != (
            expected_expectancy is None
        ) or (
            expectancy is not None
            and not math.isclose(
                expectancy,
                expected_expectancy,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("weekly expectancy mismatch")
        object.__setattr__(self, "expectancy", expectancy)
        object.__setattr__(
            self,
            "reliability_percent",
            _optional_percent(
                self.reliability_percent,
                "reliability_percent",
            ),
        )

        for name in (
            "market_performance",
            "confidence_band_performance",
            "regime_performance",
            "direction_performance",
            "time_of_day_performance",
            "contract_quality_performance",
            "spread_quality_performance",
            "liquidity_quality_performance",
            "rejected_signal_performance",
            "policy_version_performance",
        ):
            value = getattr(self, name)
            if type(value) is not tuple or any(
                type(item) is not CertificationPerformanceSliceV1
                for item in value
            ):
                raise TypeError(name)
            if len({item.key for item in value}) != len(value):
                raise ValueError(f"duplicate {name} key")

        market_prediction_total = sum(
            item.prediction_count
            for item in self.market_performance
        )
        market_closed_total = sum(
            item.closed_trade_count
            for item in self.market_performance
        )
        market_resolved_total = sum(
            item.resolved_count
            for item in self.market_performance
        )
        market_success_total = sum(
            item.success_count
            for item in self.market_performance
        )
        if market_prediction_total != self.official_prediction_count:
            raise ValueError("weekly market prediction mismatch")
        if market_closed_total != self.closed_position_count:
            raise ValueError("weekly market closed-position mismatch")
        expected_reliability = (
            market_success_total / market_resolved_total * 100.0
            if market_resolved_total
            else None
        )
        if (
            self.reliability_percent is None
        ) != (
            expected_reliability is None
        ) or (
            self.reliability_percent is not None
            and not math.isclose(
                self.reliability_percent,
                expected_reliability,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("weekly reliability mismatch")

        status = _text(self.report_status, "report_status").upper()
        if status not in _REPORT_STATUSES:
            raise ValueError("report_status")
        object.__setattr__(self, "report_status", status)
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only weekly certification report")

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["week_started_on"] = self.week_started_on.isoformat()
        result["week_ended_on"] = self.week_ended_on.isoformat()
        result["generated_at"] = self.generated_at.isoformat()
        result["daily_report_ids"] = list(self.daily_report_ids)
        for name in (
            "market_performance",
            "confidence_band_performance",
            "regime_performance",
            "direction_performance",
            "time_of_day_performance",
            "contract_quality_performance",
            "spread_quality_performance",
            "liquidity_quality_performance",
            "rejected_signal_performance",
            "policy_version_performance",
        ):
            result[name] = [
                item.to_dict()
                for item in getattr(self, name)
            ]
        return result

    def to_json(self) -> str:
        return _json(self.to_dict())

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperCertificationMonthlyReportV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "paper_certification_monthly_report.v1"
    )

    report_id: str
    month_started_on: date
    month_ended_on: date
    generated_at: datetime
    daily_report_ids: tuple[str, ...]
    weekly_report_ids: tuple[str, ...]
    starting_capital: float
    ending_capital: float
    net_pnl: float
    capital_curve: tuple[CertificationCapitalPointV1, ...]
    drawdown_periods: tuple[CertificationDrawdownPeriodV1, ...]
    maximum_drawdown_amount: float
    maximum_drawdown_percent: float
    risk_adjusted_performance: float | None
    reliability_percent: float | None
    confidence_calibration: tuple[
        CertificationConfidenceCalibrationV1, ...
    ]
    regime_contribution: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    engine_contribution: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    pillar_contribution: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    policy_version_comparison: tuple[
        CertificationPerformanceSliceV1, ...
    ]
    unresolved_audit: tuple[CertificationAuditItemV1, ...]
    excluded_record_audit: tuple[CertificationAuditItemV1, ...]
    report_status: str = "RECONCILED"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "report_id",
            _text(self.report_id, "report_id"),
        )
        start_date = _date(
            self.month_started_on,
            "month_started_on",
        )
        end_date = _date(
            self.month_ended_on,
            "month_ended_on",
        )
        if start_date > end_date:
            raise ValueError("monthly date ordering")
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )
        for name in ("daily_report_ids", "weekly_report_ids"):
            value = getattr(self, name)
            if type(value) is not tuple:
                raise TypeError(name)
            ids = tuple(_text(item, name) for item in value)
            if not ids or len(set(ids)) != len(ids):
                raise ValueError(name)
            object.__setattr__(self, name, ids)

        start = _positive(self.starting_capital, "starting_capital")
        end = _positive(self.ending_capital, "ending_capital")
        net = _number(self.net_pnl, "net_pnl")
        if not math.isclose(start + net, end, abs_tol=1e-9):
            raise ValueError("monthly capital reconciliation")
        object.__setattr__(self, "starting_capital", start)
        object.__setattr__(self, "ending_capital", end)
        object.__setattr__(self, "net_pnl", net)

        if type(self.capital_curve) is not tuple or any(
            type(item) is not CertificationCapitalPointV1
            for item in self.capital_curve
        ):
            raise TypeError("capital_curve")
        if len(self.capital_curve) != len(self.daily_report_ids):
            raise ValueError("capital curve count mismatch")
        if self.capital_curve:
            if not math.isclose(
                self.capital_curve[0].starting_capital,
                self.starting_capital,
                abs_tol=1e-9,
            ) or not math.isclose(
                self.capital_curve[-1].ending_capital,
                self.ending_capital,
                abs_tol=1e-9,
            ):
                raise ValueError("monthly capital curve endpoints")
            for previous, current in zip(
                self.capital_curve, self.capital_curve[1:]
            ):
                if not math.isclose(
                    previous.ending_capital,
                    current.starting_capital,
                    abs_tol=1e-9,
                ):
                    raise ValueError("monthly capital curve continuity")
        if type(self.drawdown_periods) is not tuple or any(
            type(item) is not CertificationDrawdownPeriodV1
            for item in self.drawdown_periods
        ):
            raise TypeError("drawdown_periods")

        drawdown = _number(
            self.maximum_drawdown_amount,
            "maximum_drawdown_amount",
        )
        drawdown_percent = _number(
            self.maximum_drawdown_percent,
            "maximum_drawdown_percent",
        )
        if drawdown < 0.0 or drawdown_percent < 0.0:
            raise ValueError("maximum drawdown")
        object.__setattr__(
            self,
            "maximum_drawdown_amount",
            drawdown,
        )
        object.__setattr__(
            self,
            "maximum_drawdown_percent",
            drawdown_percent,
        )
        object.__setattr__(
            self,
            "risk_adjusted_performance",
            _optional_number(
                self.risk_adjusted_performance,
                "risk_adjusted_performance",
            ),
        )
        object.__setattr__(
            self,
            "reliability_percent",
            _optional_percent(
                self.reliability_percent,
                "reliability_percent",
            ),
        )

        if type(self.confidence_calibration) is not tuple or any(
            type(item) is not CertificationConfidenceCalibrationV1
            for item in self.confidence_calibration
        ):
            raise TypeError("confidence_calibration")
        if len(
            {item.confidence_band for item in self.confidence_calibration}
        ) != len(self.confidence_calibration):
            raise ValueError("duplicate confidence calibration band")

        for name in (
            "regime_contribution",
            "engine_contribution",
            "pillar_contribution",
            "policy_version_comparison",
        ):
            value = getattr(self, name)
            if type(value) is not tuple or any(
                type(item) is not CertificationPerformanceSliceV1
                for item in value
            ):
                raise TypeError(name)
            if len({item.key for item in value}) != len(value):
                raise ValueError(f"duplicate {name} key")

        for name in ("unresolved_audit", "excluded_record_audit"):
            value = getattr(self, name)
            if type(value) is not tuple or any(
                type(item) is not CertificationAuditItemV1
                for item in value
            ):
                raise TypeError(name)

        status = _text(self.report_status, "report_status").upper()
        if status not in _REPORT_STATUSES:
            raise ValueError("report_status")
        object.__setattr__(self, "report_status", status)
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only monthly certification report")

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["month_started_on"] = self.month_started_on.isoformat()
        result["month_ended_on"] = self.month_ended_on.isoformat()
        result["generated_at"] = self.generated_at.isoformat()
        result["daily_report_ids"] = list(self.daily_report_ids)
        result["weekly_report_ids"] = list(self.weekly_report_ids)
        result["capital_curve"] = [
            item.to_dict()
            for item in self.capital_curve
        ]
        result["drawdown_periods"] = [
            item.to_dict()
            for item in self.drawdown_periods
        ]
        for name in (
            "confidence_calibration",
            "regime_contribution",
            "engine_contribution",
            "pillar_contribution",
            "policy_version_comparison",
        ):
            result[name] = [
                item.to_dict()
                for item in getattr(self, name)
            ]
        result["unresolved_audit"] = [
            item.to_dict()
            for item in self.unresolved_audit
        ]
        result["excluded_record_audit"] = [
            item.to_dict()
            for item in self.excluded_record_audit
        ]
        return result

    def to_json(self) -> str:
        return _json(self.to_dict())

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
