"""Fixed public-API replay matrix for P5-11 four-market ranking."""
from dataclasses import dataclass

import pytest

from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1
from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1
from services.opportunity_ranking import evaluate_four_market_opportunity_ranking, rank_four_market_opportunities
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate
from tests.test_trade_opportunity_v1 import make_opportunity


def _candidate(identity, case, *, confidence=.6, regime=.8, data=.8, liquidity=.8, execution=.8, status="READY", **changes):
    symbol, exchange = identity
    opportunity = make_opportunity(
        opportunity_id=f"{case}-{symbol}", underlying_symbol=symbol, exchange=exchange,
        trading_symbol=f"{symbol}-CALL", snapshot_id=f"snapshot-{case}-{symbol}",
    )
    values = dict(
        candidate_id=f"{case}-{symbol}", trade_opportunity=opportunity,
        trade_opportunity_available=True, opportunity_confidence=confidence,
        regime_suitability_score=regime, technical_confirmation_score=.8,
        option_chain_confirmation_score=.8, data_quality_score=data,
        liquidity_score=liquidity, execution_quality_score=execution,
        option_chain_available=True, liquidity_available=True,
        execution_quality_available=True, candidate_status=status,
    )
    values.update(changes)
    return make_candidate(identity, **values)


def _case_candidates(name, winner="NIFTY", overrides=None):
    overrides = overrides or {}
    candidates = []
    for identity in IDENTITIES:
        base_kwargs = {"confidence": .9 if identity[0] == winner else .6}
        candidate_kwargs = {**base_kwargs, **overrides.get(identity[0], {})}
        candidates.append(_candidate(identity, name, **candidate_kwargs))
    return tuple(candidates)


@dataclass(frozen=True)
class ReplayCase:
    case_name: str
    candidates: tuple
    policy: FourMarketRankingPolicyV1
    expected_selected_market: tuple[str, str] | None
    expected_tie_state: str
    expected_tied_markets: tuple[tuple[str, str], ...] = ()


def _blocked():
    return dict(status="BLOCKED", blockers=("BLOCK",), new_entries_allowed=False)


def _conflicting():
    return dict(status="CONFLICTING", contradictions=("CONFLICT",))


def _unavailable():
    return dict(data=.1)


def replay_cases():
    default = FourMarketRankingPolicyV1()
    conflict_policy = FourMarketRankingPolicyV1(allow_conflicting_candidate_to_rank=True)
    liquidity_open = FourMarketRankingPolicyV1(block_on_liquidity_failure=False)
    denominator_included = FourMarketRankingPolicyV1(exclude_unavailable_optional_scores_from_denominator=False)
    zero_penalty = FourMarketRankingPolicyV1(warning_penalty=1.0)
    cases = {}
    remaining_three = (("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))
    for symbol in ("NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"):
        name = f"CLEAR_{symbol}_WINNER"
        identity = next(identity for identity in IDENTITIES if identity[0] == symbol)
        cases[name] = ReplayCase(name, _case_candidates(name, symbol), default, identity, "NO_TIE")
    cases.update({
        "ELIGIBILITY_PRIORITY_OVER_SCORE": ReplayCase("ELIGIBILITY_PRIORITY_OVER_SCORE", _case_candidates("ELIGIBILITY_PRIORITY_OVER_SCORE", "BANKNIFTY", {"NIFTY": dict(status="READY_WITH_WARNINGS", warnings=("WARN",))}), FourMarketRankingPolicyV1(warn_on_missing_optional_reference=False), ("BANKNIFTY", "NSE"), "NO_TIE"),
        "BLOCKED_HIGH_SCORE_CANNOT_WIN": ReplayCase("BLOCKED_HIGH_SCORE_CANNOT_WIN", _case_candidates("BLOCKED_HIGH_SCORE_CANNOT_WIN", "NIFTY", {"NIFTY": _blocked()}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "UNAVAILABLE_HIGH_SCORE_CANNOT_WIN": ReplayCase("UNAVAILABLE_HIGH_SCORE_CANNOT_WIN", _case_candidates("UNAVAILABLE_HIGH_SCORE_CANNOT_WIN", "NIFTY", {"NIFTY": _unavailable()}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "CONFLICTING_DEFAULT_CANNOT_WIN": ReplayCase("CONFLICTING_DEFAULT_CANNOT_WIN", _case_candidates("CONFLICTING_DEFAULT_CANNOT_WIN", "NIFTY", {"NIFTY": _conflicting()}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "CONFLICTING_POLICY_ALLOWED": ReplayCase("CONFLICTING_POLICY_ALLOWED", _case_candidates("CONFLICTING_POLICY_ALLOWED", "NIFTY", {"NIFTY": _conflicting(), "BANKNIFTY": _blocked(), "FINNIFTY": _blocked(), "SENSEX": _blocked()}), conflict_policy, ("NIFTY", "NSE"), "NO_TIE"),
        "ONE_ELIGIBLE_MARKET": ReplayCase("ONE_ELIGIBLE_MARKET", _case_candidates("ONE_ELIGIBLE_MARKET", "NIFTY", {"BANKNIFTY": _blocked(), "FINNIFTY": _blocked(), "SENSEX": _blocked()}), default, ("NIFTY", "NSE"), "NO_TIE"),
        "ALL_INELIGIBLE": ReplayCase("ALL_INELIGIBLE", _case_candidates("ALL_INELIGIBLE", overrides={identity[0]: _blocked() for identity in IDENTITIES}), default, None, "ALL_INELIGIBLE"),
        "TWO_WAY_CANONICAL_TIE": ReplayCase("TWO_WAY_CANONICAL_TIE", _case_candidates("TWO_WAY_CANONICAL_TIE", "NIFTY", {"BANKNIFTY": dict(confidence=.9), "FINNIFTY": _blocked(), "SENSEX": _blocked()}), default, ("NIFTY", "NSE"), "TIE_RESOLVED", (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"))),
        "FOUR_WAY_CANONICAL_TIE": ReplayCase("FOUR_WAY_CANONICAL_TIE", _case_candidates("FOUR_WAY_CANONICAL_TIE", "NIFTY", {"BANKNIFTY": dict(confidence=.9), "FINNIFTY": dict(confidence=.9), "SENSEX": dict(confidence=.9)}), default, ("NIFTY", "NSE"), "TIE_RESOLVED", IDENTITIES),
        "WARNING_PENALTY_ONCE": ReplayCase("WARNING_PENALTY_ONCE", _case_candidates("WARNING_PENALTY_ONCE", "NIFTY", {"NIFTY": dict(status="READY_WITH_WARNINGS", warnings=("ONE", "TWO"))}), default, ("NIFTY", "NSE"), "NO_TIE"),
        "MISSING_OPTIONAL_PENALTY_ONCE": ReplayCase("MISSING_OPTIONAL_PENALTY_ONCE", _case_candidates("MISSING_OPTIONAL_PENALTY_ONCE", "NIFTY"), default, ("NIFTY", "NSE"), "NO_TIE"),
        "STALE_OPTIONAL_EVIDENCE": ReplayCase("STALE_OPTIONAL_EVIDENCE", _case_candidates("STALE_OPTIONAL_EVIDENCE", "NIFTY", {"NIFTY": dict(status="READY_WITH_WARNINGS", warnings=("STALE",), freshness_state="STALE")}), default, ("NIFTY", "NSE"), "NO_TIE"),
        "LIQUIDITY_BLOCK": ReplayCase("LIQUIDITY_BLOCK", _case_candidates("LIQUIDITY_BLOCK", "NIFTY", {"NIFTY": dict(liquidity=.1)}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "LIQUIDITY_NON_BLOCKING_POLICY": ReplayCase("LIQUIDITY_NON_BLOCKING_POLICY", _case_candidates("LIQUIDITY_NON_BLOCKING_POLICY", "NIFTY", {"NIFTY": dict(liquidity=.1)}), liquidity_open, ("NIFTY", "NSE"), "NO_TIE"),
        "EXECUTION_QUALITY_BLOCK": ReplayCase("EXECUTION_QUALITY_BLOCK", _case_candidates("EXECUTION_QUALITY_BLOCK", "NIFTY", {"NIFTY": dict(execution=.1)}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "SESSION_OR_ENTRY_RESTRICTION": ReplayCase("SESSION_OR_ENTRY_RESTRICTION", _case_candidates("SESSION_OR_ENTRY_RESTRICTION", "NIFTY", {"NIFTY": _blocked()}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
        "MISSING_OPTIONAL_DENOMINATOR_EXCLUDED": ReplayCase("MISSING_OPTIONAL_DENOMINATOR_EXCLUDED", _case_candidates("MISSING_OPTIONAL_DENOMINATOR_EXCLUDED", "NIFTY"), default, ("NIFTY", "NSE"), "NO_TIE"),
        "MISSING_OPTIONAL_DENOMINATOR_INCLUDED": ReplayCase("MISSING_OPTIONAL_DENOMINATOR_INCLUDED", _case_candidates("MISSING_OPTIONAL_DENOMINATOR_INCLUDED", "NIFTY"), denominator_included, ("NIFTY", "NSE"), "NO_TIE"),
        "ZERO_FINAL_SCORE_BUT_RANKABLE": ReplayCase("ZERO_FINAL_SCORE_BUT_RANKABLE", _case_candidates("ZERO_FINAL_SCORE_BUT_RANKABLE", "NIFTY", {"NIFTY": dict(status="READY_WITH_WARNINGS", warnings=("WARN",)), "BANKNIFTY": _blocked(), "FINNIFTY": _blocked(), "SENSEX": _blocked()}), zero_penalty, ("NIFTY", "NSE"), "NO_TIE"),
        "SCORE_TOLERANCE_ADVANCES_CRITERION": ReplayCase("SCORE_TOLERANCE_ADVANCES_CRITERION", _case_candidates("SCORE_TOLERANCE_ADVANCES_CRITERION", "NIFTY", {"NIFTY": dict(confidence=.8000000000001, regime=.9), "BANKNIFTY": dict(confidence=.8, regime=.8), "FINNIFTY": _blocked(), "SENSEX": _blocked()}), default, ("NIFTY", "NSE"), "NO_TIE"),
        "EXACT_THRESHOLD_BOUNDARIES": ReplayCase("EXACT_THRESHOLD_BOUNDARIES", _case_candidates("EXACT_THRESHOLD_BOUNDARIES", "NIFTY", {"NIFTY": dict(confidence=.5, regime=.5, data=.5, liquidity=.4, execution=.4)}), default, ("BANKNIFTY", "NSE"), "TIE_RESOLVED", remaining_three),
    })
    return cases


REPLAY_CASES = replay_cases()


@pytest.mark.parametrize("case", tuple(REPLAY_CASES.values()), ids=lambda case: case.case_name)
def test_replay_matrix_is_deterministic_and_matches_public_service(case):
    candidate_semantics = tuple(candidate.semantic_dict() for candidate in case.candidates)
    policy_semantic = case.policy.semantic_dict()
    first = rank_four_market_opportunities(case.candidates, case.policy)
    second = rank_four_market_opportunities(case.candidates, case.policy)
    service = evaluate_four_market_opportunity_ranking(case.candidates, case.policy)
    assert type(first) is FourMarketOpportunityRankingResultV1
    assert first.to_dict() == second.to_dict() == service.to_dict(), case.case_name
    assert first.to_json() == second.to_json() == service.to_json(), case.case_name
    assert first.semantic_dict() == second.semantic_dict() == service.semantic_dict(), case.case_name
    assert tuple((candidate.underlying_symbol, candidate.exchange) for candidate in first.candidates) == IDENTITIES
    assert first.selected_market == case.expected_selected_market
    assert first.tie_state == case.expected_tie_state
    assert first.tied_markets == case.expected_tied_markets
    if case.expected_tie_state == "TIE_RESOLVED":
        assert len(case.expected_tied_markets) >= 2 and case.expected_selected_market in case.expected_tied_markets
    else:
        assert case.expected_tied_markets == ()
    assert first.execution_mode == "PAPER" and first.live_execution_eligible is False
    assert all(0.0 <= score <= 1.0 for score in first.score_by_market.values())
    assert first.evaluated_at == case.candidates[0].evaluated_at
    assert set(first.source_timestamps) == {identity[0] for identity in IDENTITIES}
    assert first.metadata["pipeline_version"] == "P5-11H"
    assert tuple(candidate.semantic_dict() for candidate in case.candidates) == candidate_semantics
    assert case.policy.semantic_dict() == policy_semantic
    payload = first.to_dict(); payload["metadata"]["pipeline_version"] = "changed"
    assert first.metadata["pipeline_version"] == "P5-11H"
