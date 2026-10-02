"""X9-B2 five-market *descriptive* comparability, never trade eligibility or ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from services.x7.contracts_v1 import MARKETS, _aware, _sha, _text, canonical_sha256
from services.x8.contracts_v1 import X8RegimeReadinessV1, zero_authority
from services.x8.regime_description_v1 import (
    X8RegimeDescriptionV1,
    validate_x8_regime_description_v1,
)
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x9.session_prerequisites_v1 import X9SessionMatrixV1

_STATES = frozenset(
    {"COMPARABLE_CONTEXT", "REPORTED_CLOSED", "SESSION_UNKNOWN", "EVIDENCE_INCOMPLETE"}
)


def _status_from_state(description_status: str, session: str) -> str:
    if description_status != "READY_FOR_CLASSIFICATION":
        return "EVIDENCE_INCOMPLETE"
    if session == "UNKNOWN":
        return "SESSION_UNKNOWN"
    if session == "REPORTED_CLOSED":
        return "REPORTED_CLOSED"
    return "COMPARABLE_CONTEXT"


def _status(description: X8RegimeDescriptionV1, session: str) -> str:
    return _status_from_state(description.research_status, session)


@dataclass(frozen=True, slots=True)
class X9ResearchCandidateV1:
    market: str
    x8_readiness_sha256: str
    x8_description_sha256: str
    session_source_sha256: str | None
    status: str
    description_status: str
    reported_session_state: str
    schema_version: str = "X9_RESEARCH_CANDIDATE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not _sha(self.x8_readiness_sha256)
            or not _sha(self.x8_description_sha256)
            or (self.session_source_sha256 is not None and not _sha(self.session_source_sha256))
            or self.status not in _STATES
            or self.description_status not in {"UNAVAILABLE", "PARTIAL", "READY_FOR_CLASSIFICATION"}
            or self.reported_session_state not in {"UNKNOWN", "REPORTED_OPEN", "REPORTED_CLOSED"}
            or self.status
            != _status_from_state(self.description_status, self.reported_session_state)
        ):
            raise ValueError("Invalid non-trading research candidate")
        zero_authority(self, "X9_RESEARCH_CANDIDATE_V1")


@dataclass(frozen=True, slots=True)
class X9ResearchEligibilityV1:
    parent_cycle_id: str
    as_of: object
    ledger_sha256: str
    session_matrix_sha256: str
    candidates: tuple[X9ResearchCandidateV1, ...]
    comparable_market_count: int
    descriptive_status: str
    selected_market: None = None
    rankings: tuple[()] = ()
    schema_version: str = "X9_RESEARCH_ELIGIBILITY_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not _text(self.parent_cycle_id)
            or not _aware(self.as_of)
            or not _sha(self.ledger_sha256)
            or not _sha(self.session_matrix_sha256)
            or type(self.candidates) is not tuple
            or tuple(row.market for row in self.candidates) != MARKETS
            or any(type(row) is not X9ResearchCandidateV1 for row in self.candidates)
            or type(self.comparable_market_count) is not int
            or self.comparable_market_count
            != sum(row.status == "COMPARABLE_CONTEXT" for row in self.candidates)
            or self.descriptive_status
            != (
                "COMPLETE_DESCRIPTIVE"
                if self.comparable_market_count == len(MARKETS)
                else "PARTIAL_DESCRIPTIVE"
            )
            or self.selected_market is not None
            or self.rankings != ()
        ):
            raise ValueError("X9 cannot fabricate market eligibility or select a winner")
        zero_authority(self, "X9_RESEARCH_ELIGIBILITY_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def evaluate_x9_research_eligibility_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    session_matrix: X9SessionMatrixV1,
    readiness: tuple[X8RegimeReadinessV1, ...],
    descriptions: tuple[X8RegimeDescriptionV1, ...],
) -> X9ResearchEligibilityV1:
    if type(ledger) is not X9FiveMarketLedgerV1 or type(session_matrix) is not X9SessionMatrixV1:
        raise TypeError("Exact X9 ledger and session matrix required")
    if (
        session_matrix.x9_ledger_sha256 != ledger.sha256()
        or session_matrix.parent_cycle_id != ledger.parent_cycle_id
        or session_matrix.as_of != ledger.as_of
    ):
        raise ValueError("X9 session matrix does not match parent ledger")
    if (
        type(readiness) is not tuple
        or len(readiness) != len(MARKETS)
        or any(type(row) is not X8RegimeReadinessV1 for row in readiness)
        or type(descriptions) is not tuple
        or len(descriptions) != len(MARKETS)
        or any(type(row) is not X8RegimeDescriptionV1 for row in descriptions)
    ):
        raise ValueError("Exactly five typed X8 readiness and diagnostic records required")
    by_readiness = {row.market: row for row in readiness}
    by_description = {row.market: row for row in descriptions}
    if (
        set(by_readiness) != set(MARKETS)
        or len(by_readiness) != len(MARKETS)
        or set(by_description) != set(MARKETS)
        or len(by_description) != len(MARKETS)
    ):
        raise ValueError("Duplicate or missing research market")
    output = []
    for index, slot in enumerate(ledger.slots):
        original = by_readiness[slot.market]
        diagnostic = by_description[slot.market]
        session = session_matrix.prerequisites[index]
        if (
            original.sha256() != slot.x8_readiness_sha256
            or original.as_of != slot.source_as_of
            or session.market != slot.market
            or session.x8_readiness_sha256 != original.sha256()
            or session.observed_at is not None
            and session.observed_at > ledger.as_of
        ):
            raise ValueError("Unmatched upstream ledger/session/readiness provenance")
        validate_x8_regime_description_v1(readiness=original, description=diagnostic)
        output.append(
            X9ResearchCandidateV1(
                slot.market,
                original.sha256(),
                diagnostic.sha256(),
                session.session_source_sha256,
                _status(diagnostic, session.reported_state),
                diagnostic.research_status,
                session.reported_state,
            )
        )
    rows = tuple(output)
    count = sum(row.status == "COMPARABLE_CONTEXT" for row in rows)
    return X9ResearchEligibilityV1(
        ledger.parent_cycle_id,
        ledger.as_of,
        ledger.sha256(),
        session_matrix.sha256(),
        rows,
        count,
        "COMPLETE_DESCRIPTIVE" if count == len(MARKETS) else "PARTIAL_DESCRIPTIVE",
    )
