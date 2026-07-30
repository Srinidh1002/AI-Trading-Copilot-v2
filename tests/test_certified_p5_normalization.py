import pytest

from services.contracts.four_market_opportunity_ranking_result_v1 import (
    FourMarketOpportunityRankingResultV1,
)
from services.contracts.market_opportunity_candidate_v1 import (
    MarketOpportunityCandidateV1,
)
from services.paper_orchestration.certified_p5_normalization import (
    CertifiedP5SelectionV1,
    normalize_certified_p5_selection,
)


def candidate(symbol="NIFTY", exchange="NSE"):
    value = object.__new__(MarketOpportunityCandidateV1)
    object.__setattr__(value, "underlying_symbol", symbol)
    object.__setattr__(value, "exchange", exchange)
    object.__setattr__(value, "candidate_status", "READY")
    object.__setattr__(value, "analysis_allowed", True)
    object.__setattr__(value, "new_entries_allowed", True)
    object.__setattr__(value, "execution_mode", "PAPER")
    object.__setattr__(value, "live_execution_eligible", False)
    return value


def ranking(selected=None, market=None):
    selected = selected or candidate()
    market = market or ("NIFTY", "NSE")
    value = object.__new__(FourMarketOpportunityRankingResultV1)
    object.__setattr__(value, "ranking_result_id", "ranking-1")
    object.__setattr__(value, "selected_candidate", selected)
    object.__setattr__(value, "selected_market", market)
    object.__setattr__(value, "selection_confidence", 0.9)
    object.__setattr__(value, "tie_state", "NO_TIE")
    object.__setattr__(value, "blockers", ())
    object.__setattr__(value, "warnings", ())
    object.__setattr__(value, "execution_mode", "PAPER")
    object.__setattr__(value, "live_execution_eligible", False)
    return value


def test_normalizes_exact_nifty_selection():
    result = normalize_certified_p5_selection(ranking())

    assert type(result) is CertifiedP5SelectionV1
    assert result.selected_market == ("NIFTY", "NSE")
    assert type(result.selected_candidate) is MarketOpportunityCandidateV1
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_normalizes_exact_sensex_selection():
    result = normalize_certified_p5_selection(
        ranking(
            selected=candidate("SENSEX", "BSE"),
            market=("SENSEX", "BSE"),
        )
    )

    assert result.selected_market == ("SENSEX", "BSE")


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE")),
)
def test_rejects_non_certified_runtime_market(symbol, exchange):
    with pytest.raises(ValueError, match="only NIFTY and SENSEX"):
        normalize_certified_p5_selection(
            ranking(
                selected=candidate(symbol, exchange),
                market=(symbol, exchange),
            )
        )


def test_rejects_missing_selection():
    value = ranking()
    object.__setattr__(value, "selected_candidate", None)
    object.__setattr__(value, "selected_market", None)

    with pytest.raises(ValueError, match="no selected candidate"):
        normalize_certified_p5_selection(value)


def test_rejects_candidate_without_entry_authority():
    value = candidate()
    object.__setattr__(value, "new_entries_allowed", False)

    with pytest.raises(ValueError, match="new entries"):
        normalize_certified_p5_selection(ranking(selected=value))
