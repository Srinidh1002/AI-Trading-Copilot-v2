import services.opportunity_ranking.aggregate as aggregate
import services.opportunity_ranking.service as service

from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate


def test_aggregate_calls_each_pipeline_stage_once_per_canonical_candidate(monkeypatch):
    candidates = tuple(make_candidate(identity) for identity in IDENTITIES)[::-1]
    calls = {"eligibility": [], "score": [], "tie": []}
    original_eligibility = aggregate.evaluate_candidate_eligibility
    original_score = aggregate.score_market_opportunity_candidate
    original_tie = aggregate.resolve_candidate_order

    def eligibility(candidate, policy):
        calls["eligibility"].append((candidate.underlying_symbol, candidate.exchange))
        return original_eligibility(candidate, policy)

    def score(candidate, outcome, policy):
        calls["score"].append(((candidate.underlying_symbol, candidate.exchange), (outcome.underlying_symbol, outcome.exchange)))
        return original_score(candidate, outcome, policy)

    def tie(candidates, eligibility_results, score_results, policy):
        calls["tie"].append((candidates, eligibility_results, score_results))
        return original_tie(candidates, eligibility_results, score_results, policy)

    monkeypatch.setattr(aggregate, "evaluate_candidate_eligibility", eligibility)
    monkeypatch.setattr(aggregate, "score_market_opportunity_candidate", score)
    monkeypatch.setattr(aggregate, "resolve_candidate_order", tie)
    aggregate.rank_four_market_opportunities(candidates)
    assert calls["eligibility"] == list(IDENTITIES)
    assert [candidate for candidate, outcome in calls["score"]] == list(IDENTITIES)
    assert [outcome for candidate, outcome in calls["score"]] == list(IDENTITIES)
    assert len(calls["tie"]) == 1
    assert tuple((candidate.underlying_symbol, candidate.exchange) for candidate in calls["tie"][0][0]) == IDENTITIES


def test_service_delegates_to_aggregate_once_unchanged(monkeypatch):
    candidates = tuple(make_candidate(identity) for identity in IDENTITIES)
    calls = []
    sentinel = object()

    def aggregate_call(received_candidates, received_policy):
        calls.append((received_candidates, received_policy))
        return sentinel

    monkeypatch.setattr(service, "rank_four_market_opportunities", aggregate_call)
    assert service.evaluate_four_market_opportunity_ranking(candidates) is sentinel
    assert len(calls) == 1 and calls[0][0] is candidates
