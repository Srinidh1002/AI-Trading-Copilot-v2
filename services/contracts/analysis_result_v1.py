"""Side-effect-free AnalysisResult v1 contract for canonical market analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import math
from typing import Any, Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo


class AnalysisValidationError(ValueError):
    """Raised for malformed timestamps or invalid typed analysis payloads."""


class DirectionalBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT_TRANSITION = "BREAKOUT_TRANSITION"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"


class EvidenceSignal(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    EMPTY = "EMPTY"
    STALE = "STALE"
    INVALID = "INVALID"
    ERROR = "ERROR"


class AlignmentStatus(str, Enum):
    ALIGNED_BULLISH = "ALIGNED_BULLISH"
    ALIGNED_BEARISH = "ALIGNED_BEARISH"
    MIXED = "MIXED"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


VALID_DIRECTIONAL_BIASES = {item.value for item in DirectionalBias}
VALID_MARKET_REGIMES = {item.value for item in MarketRegime}
VALID_EVIDENCE_SIGNALS = {item.value for item in EvidenceSignal}
VALID_EVIDENCE_STATUSES = {item.value for item in EvidenceStatus}
VALID_ALIGNMENT_STATUSES = {item.value for item in AlignmentStatus}

CRITICAL_ENGINE_NAMES = {
    "market_data",
    "technical",
    "market_structure",
    "risk_precheck",
}

SCORE_FIELDS = (
    "technical_score",
    "structure_score",
    "candlestick_score",
    "volume_score",
    "options_score",
    "institutional_score",
    "volatility_score",
    "context_score",
    "data_quality_score",
)


def _parse_datetime(value: datetime | str, timezone_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise AnalysisValidationError("Timestamp must be ISO-8601.") from exc
    if not isinstance(value, datetime):
        raise AnalysisValidationError("Timestamp must be a datetime or ISO-8601 string.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value.astimezone(ZoneInfo(timezone_name))


def _enum_value(value: Any) -> str:
    return value.value if isinstance(value, Enum) else str(value).upper()


def _texts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _finite_score(value: Any, name: str) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AnalysisValidationError(f"{name} must be numeric.") from None
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise AnalysisValidationError(f"{name} must be finite and in 0..100.")
    return number


def _json_safe_mapping(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise AnalysisValidationError(f"{name} must be JSON-serializable.") from exc
    return dict(value)


@dataclass(slots=True)
class EvidenceSection:
    """Typed result for one analysis category."""

    status: str = EvidenceStatus.UNAVAILABLE
    signal: str = EvidenceSignal.UNAVAILABLE
    score: float | None = None
    confidence: float | None = None
    reasons: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    source_timestamp: datetime | str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timezone: str = "Asia/Kolkata"

    def __post_init__(self) -> None:
        self.status = _enum_value(self.status)
        self.signal = _enum_value(self.signal)
        if self.status not in VALID_EVIDENCE_STATUSES:
            raise AnalysisValidationError(f"Invalid evidence status: {self.status}")
        if self.signal not in VALID_EVIDENCE_SIGNALS:
            raise AnalysisValidationError(f"Invalid evidence signal: {self.signal}")
        self.score = _finite_score(self.score, "score")
        self.confidence = _finite_score(self.confidence, "confidence")
        self.reasons = _texts(self.reasons)
        self.contradictions = _texts(self.contradictions)
        self.warnings = _texts(self.warnings)
        self.errors = _texts(self.errors)
        if self.source_timestamp is not None:
            self.source_timestamp = _parse_datetime(self.source_timestamp, self.timezone)
        self.metadata = _json_safe_mapping(self.metadata, "metadata")

        if self.status in {
            EvidenceStatus.UNAVAILABLE.value,
            EvidenceStatus.EMPTY.value,
            EvidenceStatus.INVALID.value,
            EvidenceStatus.ERROR.value,
        } and self.signal in {
            EvidenceSignal.BULLISH.value,
            EvidenceSignal.BEARISH.value,
        }:
            raise AnalysisValidationError(
                f"{self.status} evidence cannot provide directional confirmation."
            )

        if self.status == EvidenceStatus.ERROR.value and not self.errors:
            self.errors = ("Evidence engine failed.",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "signal": self.signal,
            "score": self.score,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "contradictions": list(self.contradictions),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "source_timestamp": (
                self.source_timestamp.isoformat()
                if isinstance(self.source_timestamp, datetime)
                else None
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceSection":
        return cls(
            status=payload.get("status", EvidenceStatus.UNAVAILABLE.value),
            signal=payload.get("signal", EvidenceSignal.UNAVAILABLE.value),
            score=payload.get("score"),
            confidence=payload.get("confidence"),
            reasons=tuple(payload.get("reasons", ())),
            contradictions=tuple(payload.get("contradictions", ())),
            warnings=tuple(payload.get("warnings", ())),
            errors=tuple(payload.get("errors", ())),
            source_timestamp=payload.get("source_timestamp"),
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class TimeframeState:
    """Typed summary for one analyzed timeframe."""

    timeframe: str
    direction: str = DirectionalBias.UNKNOWN
    trend_strength: float | None = None
    status: str = EvidenceStatus.UNAVAILABLE
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise AnalysisValidationError("timeframe is required.")
        self.direction = _enum_value(self.direction)
        self.status = _enum_value(self.status)
        if self.direction not in VALID_DIRECTIONAL_BIASES:
            raise AnalysisValidationError("Invalid timeframe direction.")
        if self.status not in VALID_EVIDENCE_STATUSES:
            raise AnalysisValidationError("Invalid timeframe status.")
        self.trend_strength = _finite_score(self.trend_strength, "trend_strength")
        self.reasons = _texts(self.reasons)
        self.warnings = _texts(self.warnings)
        self.errors = _texts(self.errors)

        if self.status in {
            EvidenceStatus.UNAVAILABLE.value,
            EvidenceStatus.EMPTY.value,
            EvidenceStatus.INVALID.value,
            EvidenceStatus.ERROR.value,
        } and self.direction in {
            DirectionalBias.BULLISH.value,
            DirectionalBias.BEARISH.value,
        }:
            raise AnalysisValidationError(
                "Unavailable or invalid timeframe cannot provide directional confirmation."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "direction": self.direction,
            "trend_strength": self.trend_strength,
            "status": self.status,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TimeframeState":
        return cls(
            timeframe=payload.get("timeframe", ""),
            direction=payload.get("direction", DirectionalBias.UNKNOWN.value),
            trend_strength=payload.get("trend_strength"),
            status=payload.get("status", EvidenceStatus.UNAVAILABLE.value),
            reasons=tuple(payload.get("reasons", ())),
            warnings=tuple(payload.get("warnings", ())),
            errors=tuple(payload.get("errors", ())),
        )


@dataclass(slots=True)
class MultiTimeframeSummary:
    alignment: str = AlignmentStatus.INSUFFICIENT_DATA
    primary_timeframe: str | None = None
    confirmation_timeframe: str | None = None
    higher_timeframe: str | None = None
    states: Mapping[str, TimeframeState] = field(default_factory=dict)
    conflicting_timeframes: tuple[str, ...] = ()
    missing_timeframes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.alignment = _enum_value(self.alignment)
        if self.alignment not in VALID_ALIGNMENT_STATUSES:
            raise AnalysisValidationError("Invalid multi-timeframe alignment.")
        normalized: dict[str, TimeframeState] = {}
        for name, value in self.states.items():
            if not isinstance(value, TimeframeState):
                raise AnalysisValidationError(f"Invalid timeframe state: {name}")
            normalized[str(name)] = value
        self.states = normalized
        self.conflicting_timeframes = _texts(self.conflicting_timeframes)
        self.missing_timeframes = _texts(self.missing_timeframes)
        self.warnings = _texts(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alignment": self.alignment,
            "primary_timeframe": self.primary_timeframe,
            "confirmation_timeframe": self.confirmation_timeframe,
            "higher_timeframe": self.higher_timeframe,
            "states": {
                name: state.to_dict()
                for name, state in sorted(self.states.items())
            },
            "conflicting_timeframes": list(self.conflicting_timeframes),
            "missing_timeframes": list(self.missing_timeframes),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MultiTimeframeSummary":
        return cls(
            alignment=payload.get(
                "alignment", AlignmentStatus.INSUFFICIENT_DATA.value
            ),
            primary_timeframe=payload.get("primary_timeframe"),
            confirmation_timeframe=payload.get("confirmation_timeframe"),
            higher_timeframe=payload.get("higher_timeframe"),
            states={
                name: TimeframeState.from_dict(value)
                for name, value in payload.get("states", {}).items()
            },
            conflicting_timeframes=tuple(
                payload.get("conflicting_timeframes", ())
            ),
            missing_timeframes=tuple(payload.get("missing_timeframes", ())),
            warnings=tuple(payload.get("warnings", ())),
        )


@dataclass(slots=True)
class AnalysisResultV1:
    """Canonical analysis output between MarketSnapshot v1 and FinalDecision v1."""

    snapshot_id: str
    symbol: str
    created_at: datetime | str
    market_timestamp: datetime | str
    schema_version: str = "analysis_result.v1"
    analysis_id: str = field(default_factory=lambda: str(uuid4()))
    timezone: str = "Asia/Kolkata"
    market_regime: str = MarketRegime.UNKNOWN
    directional_bias: str = DirectionalBias.UNKNOWN
    direction_resolved: bool = False
    trend_strength: float | None = None
    volatility_state: str = "UNKNOWN"
    market_session: str = "UNKNOWN"
    multi_timeframe: MultiTimeframeSummary = field(
        default_factory=MultiTimeframeSummary
    )
    technical: EvidenceSection = field(default_factory=EvidenceSection)
    market_structure: EvidenceSection = field(default_factory=EvidenceSection)
    candlestick: EvidenceSection = field(default_factory=EvidenceSection)
    volume: EvidenceSection = field(default_factory=EvidenceSection)
    options: EvidenceSection = field(default_factory=EvidenceSection)
    institutional: EvidenceSection = field(default_factory=EvidenceSection)
    volatility: EvidenceSection = field(default_factory=EvidenceSection)
    context: EvidenceSection = field(default_factory=EvidenceSection)
    technical_score: float | None = None
    structure_score: float | None = None
    candlestick_score: float | None = None
    volume_score: float | None = None
    options_score: float | None = None
    institutional_score: float | None = None
    volatility_score: float | None = None
    context_score: float | None = None
    data_quality_score: float | None = None
    supporting_reasons: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    engine_errors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_timestamps: Mapping[str, str] = field(default_factory=dict)
    trace_metadata: Mapping[str, Any] = field(default_factory=dict)
    critical_error_engines: tuple[str, ...] = tuple(CRITICAL_ENGINE_NAMES)
    validation_errors: list[str] = field(default_factory=list)
    analysis_valid: bool = field(init=False)

    def __post_init__(self) -> None:
        self.created_at = _parse_datetime(self.created_at, self.timezone)
        self.market_timestamp = _parse_datetime(
            self.market_timestamp, self.timezone
        )
        self.market_regime = _enum_value(self.market_regime)
        self.directional_bias = _enum_value(self.directional_bias)

        self._validate_identity()
        self._validate_scores()
        self._validate_evidence()
        self._normalize_collections()
        self._validate_json_metadata()
        self._apply_safety_invariants()
        self.analysis_valid = not self.validation_errors

    def _validate_identity(self) -> None:
        if self.schema_version != "analysis_result.v1":
            self.validation_errors.append("Unsupported schema version.")
        for name in ("analysis_id", "snapshot_id", "symbol"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                self.validation_errors.append(f"{name} is required.")
        if self.market_regime not in VALID_MARKET_REGIMES:
            self.validation_errors.append("Invalid market regime.")
        if self.directional_bias not in VALID_DIRECTIONAL_BIASES:
            self.validation_errors.append("Invalid directional bias.")

    def _validate_scores(self) -> None:
        self.trend_strength = _finite_score(
            self.trend_strength, "trend_strength"
        )
        for name in SCORE_FIELDS:
            try:
                setattr(
                    self,
                    name,
                    _finite_score(getattr(self, name), name),
                )
            except AnalysisValidationError as exc:
                self.validation_errors.append(str(exc))

    def _validate_evidence(self) -> None:
        for name in (
            "technical",
            "market_structure",
            "candlestick",
            "volume",
            "options",
            "institutional",
            "volatility",
            "context",
        ):
            if not isinstance(getattr(self, name), EvidenceSection):
                self.validation_errors.append(
                    f"{name} must be an EvidenceSection."
                )
        if not isinstance(self.multi_timeframe, MultiTimeframeSummary):
            self.validation_errors.append(
                "multi_timeframe must be a MultiTimeframeSummary."
            )

    def _normalize_collections(self) -> None:
        self.supporting_reasons = _texts(self.supporting_reasons)
        self.contradictions = _texts(self.contradictions)
        self.missing_inputs = _texts(self.missing_inputs)
        self.warnings = _texts(self.warnings)
        self.critical_error_engines = _texts(self.critical_error_engines)

        normalized_errors: dict[str, tuple[str, ...]] = {}
        for engine, errors in self.engine_errors.items():
            normalized_errors[str(engine)] = _texts(errors)
        self.engine_errors = normalized_errors

    def _validate_json_metadata(self) -> None:
        try:
            json.dumps(self.source_timestamps, sort_keys=True)
        except (TypeError, ValueError):
            self.validation_errors.append(
                "source_timestamps must be JSON-serializable."
            )
            self.source_timestamps = {}

        try:
            json.dumps(self.trace_metadata, sort_keys=True)
        except (TypeError, ValueError):
            self.validation_errors.append(
                "trace_metadata must be JSON-serializable."
            )
            self.trace_metadata = {}

    def _apply_safety_invariants(self) -> None:
        if (
            self.directional_bias == DirectionalBias.CONFLICTED.value
            and self.direction_resolved
        ):
            self.validation_errors.append(
                "Conflicted direction cannot be marked resolved."
            )

        if (
            self.directional_bias == DirectionalBias.UNKNOWN.value
            and self.direction_resolved
        ):
            self.validation_errors.append(
                "Unknown direction cannot be marked resolved."
            )

        if self.multi_timeframe.alignment == AlignmentStatus.CONFLICTED.value:
            if self.direction_resolved:
                self.validation_errors.append(
                    "Conflicted timeframes cannot be marked direction resolved."
                )

        critical_failures = {
            name
            for name in self.critical_error_engines
            if self.engine_errors.get(name)
        }
        if critical_failures:
            self.validation_errors.append(
                "Critical analysis engines failed: "
                + ", ".join(sorted(critical_failures))
            )

        for name, section in self._evidence_items():
            if section.status == EvidenceStatus.ERROR.value and section.errors:
                if name in self.critical_error_engines:
                    message = f"Critical evidence section failed: {name}"
                    if message not in self.validation_errors:
                        self.validation_errors.append(message)

        if self.direction_resolved and self.directional_bias not in {
            DirectionalBias.BULLISH.value,
            DirectionalBias.BEARISH.value,
            DirectionalBias.NEUTRAL.value,
        }:
            self.validation_errors.append(
                "Resolved direction must be bullish, bearish, or neutral."
            )

    def _evidence_items(self) -> tuple[tuple[str, EvidenceSection], ...]:
        return (
            ("technical", self.technical),
            ("market_structure", self.market_structure),
            ("candlestick", self.candlestick),
            ("volume", self.volume),
            ("options", self.options),
            ("institutional", self.institutional),
            ("volatility", self.volatility),
            ("context", self.context),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "snapshot_id": self.snapshot_id,
            "symbol": self.symbol,
            "created_at": self.created_at.isoformat(),
            "market_timestamp": self.market_timestamp.isoformat(),
            "timezone": self.timezone,
            "market_regime": self.market_regime,
            "directional_bias": self.directional_bias,
            "direction_resolved": self.direction_resolved,
            "trend_strength": self.trend_strength,
            "volatility_state": self.volatility_state,
            "market_session": self.market_session,
            "multi_timeframe": self.multi_timeframe.to_dict(),
            "evidence": {
                name: section.to_dict()
                for name, section in self._evidence_items()
            },
            "scores": {
                name: getattr(self, name)
                for name in SCORE_FIELDS
            },
            "supporting_reasons": list(self.supporting_reasons),
            "contradictions": list(self.contradictions),
            "missing_inputs": list(self.missing_inputs),
            "warnings": list(self.warnings),
            "engine_errors": {
                name: list(errors)
                for name, errors in sorted(self.engine_errors.items())
            },
            "source_timestamps": dict(
                sorted(self.source_timestamps.items())
            ),
            "trace_metadata": dict(self.trace_metadata),
            "critical_error_engines": list(self.critical_error_engines),
            "validation_errors": list(self.validation_errors),
            "analysis_valid": self.analysis_valid,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AnalysisResultV1":
        evidence = payload.get("evidence", {})
        scores = payload.get("scores", {})
        return cls(
            schema_version=payload.get(
                "schema_version", "analysis_result.v1"
            ),
            analysis_id=payload.get("analysis_id", str(uuid4())),
            snapshot_id=payload.get("snapshot_id", ""),
            symbol=payload.get("symbol", ""),
            created_at=payload["created_at"],
            market_timestamp=payload["market_timestamp"],
            timezone=payload.get("timezone", "Asia/Kolkata"),
            market_regime=payload.get(
                "market_regime", MarketRegime.UNKNOWN.value
            ),
            directional_bias=payload.get(
                "directional_bias", DirectionalBias.UNKNOWN.value
            ),
            direction_resolved=payload.get("direction_resolved", False),
            trend_strength=payload.get("trend_strength"),
            volatility_state=payload.get("volatility_state", "UNKNOWN"),
            market_session=payload.get("market_session", "UNKNOWN"),
            multi_timeframe=MultiTimeframeSummary.from_dict(
                payload.get("multi_timeframe", {})
            ),
            technical=EvidenceSection.from_dict(
                evidence.get("technical", {})
            ),
            market_structure=EvidenceSection.from_dict(
                evidence.get("market_structure", {})
            ),
            candlestick=EvidenceSection.from_dict(
                evidence.get("candlestick", {})
            ),
            volume=EvidenceSection.from_dict(
                evidence.get("volume", {})
            ),
            options=EvidenceSection.from_dict(
                evidence.get("options", {})
            ),
            institutional=EvidenceSection.from_dict(
                evidence.get("institutional", {})
            ),
            volatility=EvidenceSection.from_dict(
                evidence.get("volatility", {})
            ),
            context=EvidenceSection.from_dict(
                evidence.get("context", {})
            ),
            technical_score=scores.get("technical_score"),
            structure_score=scores.get("structure_score"),
            candlestick_score=scores.get("candlestick_score"),
            volume_score=scores.get("volume_score"),
            options_score=scores.get("options_score"),
            institutional_score=scores.get("institutional_score"),
            volatility_score=scores.get("volatility_score"),
            context_score=scores.get("context_score"),
            data_quality_score=scores.get("data_quality_score"),
            supporting_reasons=tuple(payload.get("supporting_reasons", ())),
            contradictions=tuple(payload.get("contradictions", ())),
            missing_inputs=tuple(payload.get("missing_inputs", ())),
            warnings=tuple(payload.get("warnings", ())),
            engine_errors={
                name: tuple(errors)
                for name, errors in payload.get("engine_errors", {}).items()
            },
            source_timestamps=payload.get("source_timestamps", {}),
            trace_metadata=payload.get("trace_metadata", {}),
            critical_error_engines=tuple(
                payload.get(
                    "critical_error_engines",
                    tuple(CRITICAL_ENGINE_NAMES),
                )
            ),
            validation_errors=list(payload.get("validation_errors", ())),
        )
