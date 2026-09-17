from dataclasses import replace
from datetime import timedelta

import pytest

from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def _strong_matrix():
    return {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}


def _assert_ranking_integrity(result):
    assert tuple((candidate.underlying_symbol, candidate.exchange) for candidate in result.candidates) == CANONICAL_MARKET_IDENTITIES
    ordered = tuple((candidate.underlying_symbol, candidate.exchange) for candidate in result.ordered_candidates)
    assert tuple(result.rank_by_market[identity] for identity in ordered) == tuple(range(1, len(ordered) + 1))
    if result.selected_market is not None:
        assert result.selected_market == ordered[0]
        assert result.rank_by_market[result.selected_market] == 1
        assert result.selection_confidence == result.score_by_market[result.selected_market]
    assert result.execution_mode == 'PAPER' and result.live_execution_eligible is False


def test_complete_fresh_beats_delayed_partial_and_missing_optional():
    matrix = _strong_matrix()
    qualities = {CANONICAL_MARKET_IDENTITIES[2]: PARTIAL_OPTIONAL_PROFILE, CANONICAL_MARKET_IDENTITIES[3]: MISSING_OPTIONAL_PROFILE}
    sources = {CANONICAL_MARKET_IDENTITIES[1]: build_freshness_timestamp_profile('DELAYED')}
    result = build_ranked_four_market_result(matrix, source_timestamps_by_market=sources, component_quality_profiles_by_market=qualities)
    _assert_ranking_integrity(result)
    assert result.selected_market == CANONICAL_MARKET_IDENTITIES[0]


def test_optional_warning_matrix_remains_visible_but_complete_candidate_wins():
    matrix = _strong_matrix()
    sources = {}
    for identity, component, offset in ((CANONICAL_MARKET_IDENTITIES[1], 'broader_market', -301), (CANONICAL_MARKET_IDENTITIES[2], 'external_context', 6)):
        timestamps = dict(build_freshness_timestamp_profile('FRESH'))
        timestamps[component] = REPLAY_EVALUATED_AT + timedelta(seconds=offset)
        sources[identity] = timestamps
    result = build_ranked_four_market_result(matrix, source_timestamps_by_market=sources, component_quality_profiles_by_market={CANONICAL_MARKET_IDENTITIES[3]: OPTIONAL_PROVIDER_BLOCKED_PROFILE})
    _assert_ranking_integrity(result)
    assert result.selected_market == CANONICAL_MARKET_IDENTITIES[0]
    assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[3]] is not None


@pytest.mark.parametrize('component,timestamp', (('market_regime', REPLAY_EVALUATED_AT - timedelta(seconds=301)), ('market_regime', REPLAY_EVALUATED_AT + timedelta(seconds=6))))
def test_required_stale_or_future_candidate_cannot_win(component, timestamp):
    matrix = _strong_matrix()
    sources = dict(build_freshness_timestamp_profile('FRESH'))
    sources[component] = timestamp
    profile = classify_fixture_freshness_profile(sources)
    result = build_ranked_four_market_result(matrix, source_timestamps_by_market={CANONICAL_MARKET_IDENTITIES[0]: sources}, component_freshness_profiles_by_market={CANONICAL_MARKET_IDENTITIES[0]: profile})
    _assert_ranking_integrity(result)
    assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None
    assert result.selected_market != CANONICAL_MARKET_IDENTITIES[0]


def test_required_provider_blocked_and_all_ineligible_matrices():
    matrix = _strong_matrix()
    result = build_ranked_four_market_result(matrix, component_quality_profiles_by_market={CANONICAL_MARKET_IDENTITIES[0]: REQUIRED_PROVIDER_BLOCKED_PROFILE})
    assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None and result.selected_market != CANONICAL_MARKET_IDENTITIES[0]
    all_blocked = build_ranked_four_market_result(matrix, component_quality_profiles_by_market={identity: REQUIRED_PROVIDER_BLOCKED_PROFILE for identity in CANONICAL_MARKET_IDENTITIES})
    assert all_blocked.tie_state == 'ALL_INELIGIBLE' and all_blocked.selected_market is None
    assert all(rank is None for rank in all_blocked.rank_by_market.values())


@pytest.mark.parametrize('winner', CANONICAL_MARKET_IDENTITIES)
def test_each_market_can_win_a_fresh_complete_good_matrix(winner):
    candidates = list(build_four_market_candidate_set(_strong_matrix()))
    index = CANONICAL_MARKET_IDENTITIES.index(winner)
    candidates[index] = replace(candidates[index], opportunity_confidence=.95)
    result = rank_four_market_opportunities(tuple(reversed(candidates)))
    _assert_ranking_integrity(result)
    assert result.selected_market == winner


def test_missing_required_evaluator_report_is_excluded_from_aggregate(monkeypatch):
    import services.opportunity_ranking.aggregate as aggregate

    candidates = build_four_market_candidate_set(_strong_matrix())
    case = build_missing_required_evaluation_case(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH)
    case = replace(case, baseline_candidate=candidates[0])
    monkeypatch.setattr(aggregate, 'evaluate_candidate_eligibility', case.evaluator_patch(aggregate.evaluate_candidate_eligibility))
    result = aggregate.rank_four_market_opportunities(candidates)
    assert result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None
    assert result.selected_market != CANONICAL_MARKET_IDENTITIES[0]
