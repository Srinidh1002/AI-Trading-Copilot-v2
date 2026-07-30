from __future__ import annotations

from dataclasses import dataclass

from services.contracts.four_market_opportunity_ranking_result_v1 import (
    FourMarketOpportunityRankingResultV1,
)
from services.contracts.market_opportunity_candidate_v1 import (
    MarketOpportunityCandidateV1,
)


_ALLOWED_CERTIFIED_IDENTITIES = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}


@dataclass(frozen=True, slots=True)
class CertifiedP5SelectionV1:
    ranking_result_id: str
    selected_candidate: MarketOpportunityCandidateV1
    selected_market: tuple[str, str]
    selection_confidence: float
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_p5_selection.v1"

    def __post_init__(self) -> None:
        if type(self.ranking_result_id) is not str or not self.ranking_result_id.strip():
            raise ValueError("ranking_result_id must be non-empty")
        if type(self.selected_candidate) is not MarketOpportunityCandidateV1:
            raise TypeError(
                "selected_candidate must be exact MarketOpportunityCandidateV1"
            )
        if type(self.selected_market) is not tuple or len(self.selected_market) != 2:
            raise TypeError("selected_market must be an exact market identity tuple")

        identity = (
            str(self.selected_market[0]).strip().upper(),
            str(self.selected_market[1]).strip().upper(),
        )
        if identity not in _ALLOWED_CERTIFIED_IDENTITIES:
            raise ValueError("certified PAPER runtime supports only NIFTY and SENSEX")
        object.__setattr__(self, "selected_market", identity)

        candidate_identity = (
            self.selected_candidate.underlying_symbol,
            self.selected_candidate.exchange,
        )
        if candidate_identity != identity:
            raise ValueError("selected candidate market identity mismatch")
        if self.selected_candidate.candidate_status not in {
            "READY",
            "READY_WITH_WARNINGS",
        }:
            raise ValueError("selected candidate is not P6-eligible")
        if not self.selected_candidate.analysis_allowed:
            raise ValueError("selected candidate does not permit analysis")
        if not self.selected_candidate.new_entries_allowed:
            raise ValueError("selected candidate does not permit new entries")
        if self.selected_candidate.execution_mode != "PAPER":
            raise ValueError("selected candidate must be PAPER-only")
        if self.selected_candidate.live_execution_eligible is not False:
            raise ValueError("selected candidate cannot be live eligible")

        if isinstance(self.selection_confidence, bool) or type(
            self.selection_confidence
        ) not in (int, float):
            raise TypeError("selection_confidence must be numeric")
        confidence = float(self.selection_confidence)
        if not 0 <= confidence <= 1:
            raise ValueError("selection_confidence must be between zero and one")
        object.__setattr__(self, "selection_confidence", confidence)

        if type(self.warnings) is not tuple:
            raise TypeError("warnings must be an exact tuple")
        object.__setattr__(
            self,
            "warnings",
            tuple(dict.fromkeys(str(item).strip() for item in self.warnings if str(item).strip())),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_p5_selection.v1":
            raise ValueError("unsupported schema_version")


def normalize_certified_p5_selection(
    ranking_result: FourMarketOpportunityRankingResultV1,
) -> CertifiedP5SelectionV1:
    if type(ranking_result) is not FourMarketOpportunityRankingResultV1:
        raise TypeError(
            "ranking_result must be exact FourMarketOpportunityRankingResultV1"
        )
    if ranking_result.execution_mode != "PAPER":
        raise ValueError("ranking result must be PAPER-only")
    if ranking_result.live_execution_eligible is not False:
        raise ValueError("ranking result cannot be live eligible")
    if ranking_result.selected_candidate is None:
        raise ValueError("ranking result has no selected candidate")
    if ranking_result.selected_market is None:
        raise ValueError("ranking result has no selected market")
    if ranking_result.tie_state == "ALL_INELIGIBLE":
        raise ValueError("ranking result is all-ineligible")
    if ranking_result.blockers:
        raise ValueError("ranking result contains blockers")

    return CertifiedP5SelectionV1(
        ranking_result_id=ranking_result.ranking_result_id,
        selected_candidate=ranking_result.selected_candidate,
        selected_market=ranking_result.selected_market,
        selection_confidence=ranking_result.selection_confidence,
        warnings=ranking_result.warnings,
    )
