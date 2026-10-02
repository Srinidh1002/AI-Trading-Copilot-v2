"""X9-B3 cross-market research comparability safeguards; never a ranker."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from services.x7.contracts_v1 import MARKETS, _sha, canonical_sha256
from services.x8.contracts_v1 import zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x9.research_eligibility_v1 import X9ResearchEligibilityV1


@dataclass(frozen=True, slots=True)
class X9ComparisonSafeguardsV1:
    parent_cycle_id: str
    ledger_sha256: str
    eligibility_sha256: str
    max_capture_skew_seconds: float
    per_market: tuple[tuple[str, str, tuple[str, ...]], ...]
    ready_for_descriptive_comparison: bool
    shared_source_warnings: tuple[str, ...]
    selected_market: None = None
    rankings: tuple[()] = ()
    schema_version: str = "X9_COMPARISON_SAFEGUARDS_V1"
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
            or not _sha(self.ledger_sha256)
            or not _sha(self.eligibility_sha256)
            or type(self.max_capture_skew_seconds) is not float
            or not math.isfinite(self.max_capture_skew_seconds)
            or self.max_capture_skew_seconds <= 0
            or type(self.per_market) is not tuple
            or tuple(row[0] for row in self.per_market) != MARKETS
            or any(
                type(row) is not tuple
                or len(row) != 3
                or row[1]
                not in {
                    "COMPARABLE_CONTEXT",
                    "TIMING_SKEW",
                    "REPORTED_CLOSED",
                    "SESSION_UNKNOWN",
                    "EVIDENCE_INCOMPLETE",
                }
                or type(row[2]) is not tuple
                for row in self.per_market
            )
            or type(self.ready_for_descriptive_comparison) is not bool
            or self.ready_for_descriptive_comparison
            != all(row[1] == "COMPARABLE_CONTEXT" for row in self.per_market)
            or type(self.shared_source_warnings) is not tuple
            or self.selected_market is not None
            or self.rankings != ()
        ):
            raise ValueError("X9 comparison safeguard must retain all five unranked markets")
        zero_authority(self, "X9_COMPARISON_SAFEGUARDS_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def audit_x9_comparison_safeguards_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    eligibility: X9ResearchEligibilityV1,
    max_capture_skew_seconds: float,
    shared_source_warnings: tuple[str, ...] = (),
) -> X9ComparisonSafeguardsV1:
    if type(ledger) is not X9FiveMarketLedgerV1 or type(eligibility) is not X9ResearchEligibilityV1:
        raise TypeError("Exact X9 ledger and eligibility required")
    if (
        ledger.sha256() != eligibility.ledger_sha256
        or ledger.parent_cycle_id != eligibility.parent_cycle_id
        or ledger.as_of != eligibility.as_of
    ):
        raise ValueError("X9 ledger and eligibility are from different cycles")
    if (
        type(max_capture_skew_seconds) not in (int, float)
        or not math.isfinite(max_capture_skew_seconds)
        or max_capture_skew_seconds <= 0
    ):
        raise ValueError("Positive finite skew budget required")
    if type(shared_source_warnings) is not tuple or any(
        type(w) is not str or not w.strip() for w in shared_source_warnings
    ):
        raise ValueError("Shared-source warnings must be explicit nonblank strings")
    rows = []
    for slot, candidate in zip(ledger.slots, eligibility.candidates, strict=True):
        if slot.market != candidate.market:
            raise ValueError("Out-of-order X9 market candidate")
        skew = (ledger.as_of - slot.source_as_of).total_seconds()
        state = (
            candidate.status
            if candidate.status != "COMPARABLE_CONTEXT"
            else "TIMING_SKEW"
            if skew > max_capture_skew_seconds
            else "COMPARABLE_CONTEXT"
        )
        reasons = (
            ()
            if state == "COMPARABLE_CONTEXT"
            else ("CAPTURE_TIME_SKEW",)
            if state == "TIMING_SKEW"
            else (state,)
        )
        rows.append((slot.market, state, reasons))
    # Shared-source warnings prevent unsupported independence claims; they do
    # not silently change the family status or invent statistical correlations.
    return X9ComparisonSafeguardsV1(
        ledger.parent_cycle_id,
        ledger.sha256(),
        eligibility.sha256(),
        float(max_capture_skew_seconds),
        tuple(rows),
        all(row[1] == "COMPARABLE_CONTEXT" for row in rows),
        tuple(sorted(set(shared_source_warnings))),
    )


def validate_x9_comparison_safeguards_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    eligibility: X9ResearchEligibilityV1,
    safeguards: X9ComparisonSafeguardsV1,
) -> None:
    """Recalculate all descriptive rows from original anchored X9 sources."""
    if type(safeguards) is not X9ComparisonSafeguardsV1:
        raise TypeError("Exact immutable X9 safeguards required")
    original = audit_x9_comparison_safeguards_v1(
        ledger=ledger,
        eligibility=eligibility,
        max_capture_skew_seconds=safeguards.max_capture_skew_seconds,
        shared_source_warnings=safeguards.shared_source_warnings,
    )
    if original != safeguards:
        raise ValueError("X9 comparison report differs from original five-market sources")
