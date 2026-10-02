"""Five-market descriptive session-evidence matrix, without market ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, canonical_sha256
from services.x8.contracts_v1 import X8RegimeReadinessV1, zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1

STATES = frozenset({"REPORTED_OPEN", "REPORTED_CLOSED", "UNKNOWN"})


@dataclass(frozen=True, slots=True)
class X9SessionPrerequisiteV1:
    market: str
    x8_readiness_sha256: str
    session_source_sha256: str | None
    observed_at: datetime | None
    reported_state: str
    schema_version: str = "X9_SESSION_PREREQUISITE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKETS or not _sha(self.x8_readiness_sha256):
            raise ValueError("Invalid prerequisite market/X8 binding")
        if self.reported_state not in STATES:
            raise ValueError("Invalid descriptive session state")
        if self.reported_state == "UNKNOWN":
            if self.session_source_sha256 is not None or self.observed_at is not None:
                raise ValueError("Unknown session must remain unproven")
        elif not _sha(self.session_source_sha256) or not _aware(self.observed_at):
            raise ValueError("Reported session requires supplied source provenance")
        zero_authority(self, "X9_SESSION_PREREQUISITE_V1")


@dataclass(frozen=True, slots=True)
class X9SessionMatrixV1:
    parent_cycle_id: str
    as_of: datetime
    x9_ledger_sha256: str
    prerequisites: tuple[X9SessionPrerequisiteV1, ...]
    status: str
    reported_index_overlap: bool
    selected_market: None = None
    rankings: tuple[()] = ()
    schema_version: str = "X9_SESSION_MATRIX_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not self.parent_cycle_id
            or not _aware(self.as_of)
            or not _sha(self.x9_ledger_sha256)
            or type(self.prerequisites) is not tuple
            or tuple(row.market for row in self.prerequisites) != MARKETS
            or any(
                row.observed_at is not None and row.observed_at > self.as_of
                for row in self.prerequisites
            )
            or self.selected_market is not None
            or self.rankings != ()
        ):
            raise ValueError("Five-market descriptive session matrix only")
        status = (
            "COMPLETE_DESCRIPTIVE"
            if all(row.reported_state != "UNKNOWN" for row in self.prerequisites)
            else "INCOMPLETE_DESCRIPTIVE"
        )
        overlap = all(
            self.prerequisites[index].reported_state == "REPORTED_OPEN" for index in (0, 1)
        )
        if self.status != status or self.reported_index_overlap is not overlap:
            raise ValueError("Session matrix cannot invent complete reports or overlap")
        zero_authority(self, "X9_SESSION_MATRIX_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def build_x9_session_matrix_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    readiness: tuple[X8RegimeReadinessV1, ...],
    reported_states: tuple[tuple[str, str], ...],
) -> X9SessionMatrixV1:
    """Consume caller-reported session states; never infer exchange-open truth."""
    if type(ledger) is not X9FiveMarketLedgerV1:
        raise TypeError("A frozen X9 ledger is required")
    if (
        type(readiness) is not tuple
        or len(readiness) != len(MARKETS)
        or any(type(row) is not X8RegimeReadinessV1 for row in readiness)
    ):
        raise ValueError("Exactly five X8 readiness results are required")
    if (
        type(reported_states) is not tuple
        or len(reported_states) != len(MARKETS)
        or any(
            type(row) is not tuple or len(row) != 2 or row[0] not in MARKETS or row[1] not in STATES
            for row in reported_states
        )
    ):
        raise ValueError("One declared session state per market is required")
    by_market = {row.market: row for row in readiness}
    states = dict(reported_states)
    if len(by_market) != len(MARKETS) or len(states) != len(MARKETS):
        raise ValueError("Duplicate or missing market session evidence")
    projections = []
    for slot in ledger.slots:
        record = by_market[slot.market]
        if record.sha256() != slot.x8_readiness_sha256 or record.as_of != slot.source_as_of:
            raise ValueError("X8 readiness does not match the frozen X9 slot")
        session = next((row for row in record.evidence if row.family == "MARKET_SESSION"), None)
        declared = states[slot.market]
        if session is None or session.state != "AVAILABLE" or not session.point_in_time_verified:
            if declared != "UNKNOWN":
                raise ValueError("Unverified or missing session cannot be reported open/closed")
            projections.append(
                X9SessionPrerequisiteV1(
                    slot.market,
                    record.sha256(),
                    None,
                    None,
                    "UNKNOWN",
                )
            )
        else:
            projections.append(
                X9SessionPrerequisiteV1(
                    slot.market,
                    record.sha256(),
                    session.source_sha256 if declared != "UNKNOWN" else None,
                    session.observed_at if declared != "UNKNOWN" else None,
                    declared,
                )
            )
    ordered = tuple(projections)
    return X9SessionMatrixV1(
        ledger.parent_cycle_id,
        ledger.as_of,
        ledger.sha256(),
        ordered,
        "COMPLETE_DESCRIPTIVE"
        if all(row.reported_state != "UNKNOWN" for row in ordered)
        else "INCOMPLETE_DESCRIPTIVE",
        all(ordered[i].reported_state == "REPORTED_OPEN" for i in (0, 1)),
    )
