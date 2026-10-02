"""X9-B4 cross-module replay: original five-market inputs, no market selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from services.x7.contracts_v1 import MARKETS, _sha, canonical_sha256
from services.x8.contracts_v1 import X8RegimeReadinessV1, zero_authority
from services.x8.regime_description_v1 import X8RegimeDescriptionV1
from services.x9.comparison_safeguards_v1 import (
    X9ComparisonSafeguardsV1,
    audit_x9_comparison_safeguards_v1,
)
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x9.research_eligibility_v1 import evaluate_x9_research_eligibility_v1
from services.x9.session_prerequisites_v1 import X9SessionMatrixV1, build_x9_session_matrix_v1


@dataclass(frozen=True, slots=True)
class X9ProvenanceReplayV1:
    parent_cycle_id: str
    ledger_sha256: str
    session_matrix_sha256: str
    eligibility_sha256: str
    safeguards_sha256: str
    market_readiness_hashes: tuple[tuple[str, str], ...]
    market_description_hashes: tuple[tuple[str, str], ...]
    status: str
    selected_market: None = None
    rankings: tuple[()] = ()
    schema_version: str = "X9_PROVENANCE_REPLAY_V1"
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
            or any(
                not _sha(x)
                for x in (
                    self.ledger_sha256,
                    self.session_matrix_sha256,
                    self.eligibility_sha256,
                    self.safeguards_sha256,
                )
            )
            or self.status not in {"REPLAYED_DESCRIPTIVE", "INCOMPLETE_DESCRIPTIVE"}
            or tuple(m for m, _ in self.market_readiness_hashes) != MARKETS
            or tuple(m for m, _ in self.market_description_hashes) != MARKETS
            or any(
                not _sha(v)
                for _, v in self.market_readiness_hashes + self.market_description_hashes
            )
            or self.selected_market is not None
            or self.rankings != ()
        ):
            raise ValueError("Invalid unranked five-market provenance result")
        zero_authority(self, "X9_PROVENANCE_REPLAY_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def replay_x9_provenance_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    expected_ledger_sha256: str,
    matrix: X9SessionMatrixV1,
    expected_matrix_sha256: str,
    readiness: tuple[X8RegimeReadinessV1, ...],
    descriptions: tuple[X8RegimeDescriptionV1, ...],
    eligibility: object,
    expected_eligibility_sha256: str,
    safeguards: X9ComparisonSafeguardsV1,
    expected_safeguards_sha256: str,
) -> X9ProvenanceReplayV1:
    from services.x9.research_eligibility_v1 import X9ResearchEligibilityV1

    if (
        type(ledger) is not X9FiveMarketLedgerV1
        or type(matrix) is not X9SessionMatrixV1
        or type(eligibility) is not X9ResearchEligibilityV1
        or type(safeguards) is not X9ComparisonSafeguardsV1
    ):
        raise TypeError("Original immutable X9 records required")
    values = (
        (ledger, expected_ledger_sha256),
        (matrix, expected_matrix_sha256),
        (eligibility, expected_eligibility_sha256),
        (safeguards, expected_safeguards_sha256),
    )
    if any(not _sha(digest) or original.sha256() != digest for original, digest in values):
        raise ValueError("Detached provenance digest mismatch")
    if (
        type(readiness) is not tuple
        or type(descriptions) is not tuple
        or len(readiness) != len(MARKETS)
        or len(descriptions) != len(MARKETS)
        or tuple(x.market for x in readiness) != MARKETS
        or tuple(x.market for x in descriptions) != MARKETS
    ):
        raise ValueError("Exactly five ordered original market references required")
    # Rebuild the session matrix using its original reported states and no
    # new policy/canonical calendar inference.
    reproduced_matrix = build_x9_session_matrix_v1(
        ledger=ledger,
        readiness=readiness,
        reported_states=tuple((p.market, p.reported_state) for p in matrix.prerequisites),
    )
    if reproduced_matrix != matrix:
        raise ValueError("Original session matrix cannot be reproduced")
    reproduced_eligibility = evaluate_x9_research_eligibility_v1(
        ledger=ledger,
        session_matrix=matrix,
        readiness=readiness,
        descriptions=descriptions,
    )
    if reproduced_eligibility != eligibility:
        raise ValueError("Original descriptive eligibility cannot be reproduced")
    reproduced_safeguards = audit_x9_comparison_safeguards_v1(
        ledger=ledger,
        eligibility=eligibility,
        max_capture_skew_seconds=safeguards.max_capture_skew_seconds,
        shared_source_warnings=safeguards.shared_source_warnings,
    )
    if reproduced_safeguards != safeguards:
        raise ValueError("Original comparison safeguards cannot be reproduced")
    return X9ProvenanceReplayV1(
        ledger.parent_cycle_id,
        ledger.sha256(),
        matrix.sha256(),
        eligibility.sha256(),
        safeguards.sha256(),
        tuple((r.market, r.sha256()) for r in readiness),
        tuple((d.market, d.sha256()) for d in descriptions),
        "REPLAYED_DESCRIPTIVE"
        if safeguards.ready_for_descriptive_comparison
        else "INCOMPLETE_DESCRIPTIVE",
    )
