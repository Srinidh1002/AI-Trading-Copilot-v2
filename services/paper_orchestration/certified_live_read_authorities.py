from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)
from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)


DataReader = Callable[[PaperOrchestrationCycleInputV1], Mapping[str, Any]]
AnalysisReader = Callable[
    [PaperOrchestrationCycleInputV1, "CertifiedLiveDataResultV1"],
    Mapping[str, Any],
]
OpportunityReader = Callable[
    [
        PaperOrchestrationCycleInputV1,
        "CertifiedLiveAnalysisResultV1",
        MarketSessionValidationV1,
    ],
    Mapping[str, Any],
]


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _tuple_text(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if type(value) is str:
        value = (value,)
    try:
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    except TypeError as exc:
        raise TypeError("text collection must be iterable") from exc


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return dict(value)


@dataclass(frozen=True, slots=True)
class CertifiedLiveDataResultV1:
    observation_id: str
    underlying_symbol: str
    exchange: str
    symboltoken: str
    market_timestamp: datetime
    received_at: datetime
    spot_price: float
    payload: Mapping[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_live_data_result.v1"

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "underlying_symbol",
            "exchange",
            "symboltoken",
        ):
            value = _text(getattr(self, name), name)
            if name in {"underlying_symbol", "exchange"}:
                value = value.upper()
            object.__setattr__(self, name, value)

        market_timestamp = _aware(
            self.market_timestamp,
            "market_timestamp",
        )
        received_at = _aware(self.received_at, "received_at")
        if received_at < market_timestamp:
            raise ValueError("received_at cannot precede market_timestamp")

        if type(self.spot_price) not in (int, float) or isinstance(
            self.spot_price,
            bool,
        ):
            raise TypeError("spot_price must be numeric")
        spot_price = float(self.spot_price)
        if spot_price <= 0:
            raise ValueError("spot_price must be greater than zero")
        object.__setattr__(self, "spot_price", spot_price)

        object.__setattr__(
            self,
            "payload",
            _mapping(self.payload, "payload"),
        )
        object.__setattr__(
            self,
            "blockers",
            _tuple_text(self.blockers),
        )
        object.__setattr__(
            self,
            "warnings",
            _tuple_text(self.warnings),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError("broker order submission must remain disabled")
        if self.schema_version != "certified_live_data_result.v1":
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class CertifiedLiveAnalysisResultV1:
    observation_id: str
    underlying_symbol: str
    exchange: str
    symboltoken: str
    market_timestamp: datetime
    analysis: Mapping[str, Any]
    candidate: MarketAnalysisCandidateV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_live_analysis_result.v1"

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "underlying_symbol",
            "exchange",
            "symboltoken",
        ):
            value = _text(getattr(self, name), name)
            if name in {"underlying_symbol", "exchange"}:
                value = value.upper()
            object.__setattr__(self, name, value)

        object.__setattr__(
            self,
            "market_timestamp",
            _aware(self.market_timestamp, "market_timestamp"),
        )
        object.__setattr__(
            self,
            "analysis",
            _mapping(self.analysis, "analysis"),
        )

        if self.candidate is not None:
            if type(self.candidate) is not MarketAnalysisCandidateV1:
                raise TypeError(
                    "candidate must be exact MarketAnalysisCandidateV1 or None"
                )
            candidate_identity = (
                self.candidate.observation_id,
                self.candidate.underlying_symbol,
                self.candidate.exchange,
                self.candidate.symboltoken,
                self.candidate.market_timestamp,
            )
            result_identity = (
                self.observation_id,
                self.underlying_symbol,
                self.exchange,
                self.symboltoken,
                self.market_timestamp,
            )
            if candidate_identity != result_identity:
                raise ValueError(
                    "candidate identity does not match analysis result"
                )

        object.__setattr__(
            self,
            "blockers",
            _tuple_text(self.blockers),
        )
        object.__setattr__(
            self,
            "warnings",
            _tuple_text(self.warnings),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError("broker order submission must remain disabled")
        if self.schema_version != "certified_live_analysis_result.v1":
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class CertifiedLiveOpportunityResultV1:
    opportunity_status: str
    decision: str
    underlying_symbol: str
    exchange: str
    market_timestamp: datetime
    evidence: Mapping[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_live_opportunity_result.v1"

    def __post_init__(self) -> None:
        status = _text(
            self.opportunity_status,
            "opportunity_status",
        ).upper()
        if status not in {
            "READY",
            "NO_ACTION",
            "BLOCKED",
            "CONFLICTING",
            "FAILED",
        }:
            raise ValueError("unsupported opportunity_status")
        object.__setattr__(self, "opportunity_status", status)
        object.__setattr__(
            self,
            "decision",
            _text(self.decision, "decision").upper(),
        )
        object.__setattr__(
            self,
            "underlying_symbol",
            _text(
                self.underlying_symbol,
                "underlying_symbol",
            ).upper(),
        )
        object.__setattr__(
            self,
            "exchange",
            _text(self.exchange, "exchange").upper(),
        )
        object.__setattr__(
            self,
            "market_timestamp",
            _aware(self.market_timestamp, "market_timestamp"),
        )
        object.__setattr__(
            self,
            "evidence",
            _mapping(self.evidence, "evidence"),
        )
        blockers = _tuple_text(self.blockers)
        warnings = _tuple_text(self.warnings)
        if status in {"BLOCKED", "CONFLICTING", "FAILED"} and not blockers:
            raise ValueError(
                "blocked/conflicting/failed opportunity needs blockers"
            )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError("broker order submission must remain disabled")
        if self.schema_version != "certified_live_opportunity_result.v1":
            raise ValueError("unsupported schema_version")


class CertifiedLiveDataAuthority:
    """Read one immutable market observation through an injected reader."""

    def __init__(self, *, reader: DataReader) -> None:
        if not callable(reader):
            raise TypeError("reader must be callable")
        self.reader = reader

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> CertifiedLiveDataResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )

        raw = _mapping(self.reader(cycle_input), "data reader result")
        result = CertifiedLiveDataResultV1(
            observation_id=cycle_input.observation_id,
            underlying_symbol=cycle_input.underlying_symbol,
            exchange=cycle_input.exchange,
            symboltoken=raw.get("symboltoken"),
            market_timestamp=raw.get(
                "market_timestamp",
                cycle_input.market_timestamp,
            ),
            received_at=raw.get(
                "received_at",
                cycle_input.received_at,
            ),
            spot_price=raw.get("spot_price"),
            payload=raw.get("payload", raw),
            blockers=raw.get("blockers", ()),
            warnings=raw.get("warnings", ()),
        )
        if result.underlying_symbol != cycle_input.underlying_symbol:
            raise ValueError("data result underlying identity mismatch")
        if result.exchange != cycle_input.exchange:
            raise ValueError("data result exchange identity mismatch")
        return result


class CertifiedSessionAuthority:
    """Reuse the exact session validation already carried by the cycle."""

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
    ) -> MarketSessionValidationV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )
        if type(data_result) is not CertifiedLiveDataResultV1:
            raise TypeError(
                "data_result must be exact CertifiedLiveDataResultV1"
            )

        session = cycle_input.session_validation
        if type(session) is not MarketSessionValidationV1:
            raise TypeError(
                "session_validation must be exact MarketSessionValidationV1"
            )
        if session.symbol != data_result.underlying_symbol:
            raise ValueError("session/data symbol identity mismatch")
        if session.exchange != data_result.exchange:
            raise ValueError("session/data exchange identity mismatch")
        if session.market_timestamp != data_result.market_timestamp:
            raise ValueError("session/data timestamp identity mismatch")
        return session


class CertifiedLiveAnalysisAuthority:
    """Run read-only analysis through an injected analysis boundary."""

    def __init__(self, *, reader: AnalysisReader) -> None:
        if not callable(reader):
            raise TypeError("reader must be callable")
        self.reader = reader

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        data_result: CertifiedLiveDataResultV1,
        session_result: MarketSessionValidationV1,
    ) -> CertifiedLiveAnalysisResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )
        if type(data_result) is not CertifiedLiveDataResultV1:
            raise TypeError(
                "data_result must be exact CertifiedLiveDataResultV1"
            )
        if type(session_result) is not MarketSessionValidationV1:
            raise TypeError(
                "session_result must be exact MarketSessionValidationV1"
            )
        if not session_result.analysis_allowed:
            raise RuntimeError("analysis is not allowed by session authority")

        raw = _mapping(
            self.reader(cycle_input, data_result),
            "analysis reader result",
        )
        return CertifiedLiveAnalysisResultV1(
            observation_id=cycle_input.observation_id,
            underlying_symbol=cycle_input.underlying_symbol,
            exchange=cycle_input.exchange,
            symboltoken=data_result.symboltoken,
            market_timestamp=data_result.market_timestamp,
            analysis=raw.get("analysis", raw),
            candidate=raw.get("candidate"),
            blockers=raw.get("blockers", ()),
            warnings=raw.get("warnings", ()),
        )


class CertifiedLiveOpportunityAuthority:
    """Normalize read-only opportunity evidence into P9 stage semantics."""

    def __init__(self, *, reader: OpportunityReader) -> None:
        if not callable(reader):
            raise TypeError("reader must be callable")
        self.reader = reader

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        analysis_result: CertifiedLiveAnalysisResultV1,
        session_result: MarketSessionValidationV1,
    ) -> CertifiedLiveOpportunityResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )
        if type(analysis_result) is not CertifiedLiveAnalysisResultV1:
            raise TypeError(
                "analysis_result must be exact "
                "CertifiedLiveAnalysisResultV1"
            )
        if type(session_result) is not MarketSessionValidationV1:
            raise TypeError(
                "session_result must be exact MarketSessionValidationV1"
            )

        raw = _mapping(
            self.reader(
                cycle_input,
                analysis_result,
                session_result,
            ),
            "opportunity reader result",
        )
        return CertifiedLiveOpportunityResultV1(
            opportunity_status=raw.get(
                "opportunity_status",
                raw.get("status"),
            ),
            decision=raw.get("decision"),
            underlying_symbol=cycle_input.underlying_symbol,
            exchange=cycle_input.exchange,
            market_timestamp=cycle_input.market_timestamp,
            evidence=raw.get("evidence", raw),
            blockers=raw.get("blockers", ()),
            warnings=raw.get("warnings", ()),
        )
