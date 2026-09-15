from dataclasses import replace

import pytest

from services.analysis.market_analysis_candidate_composer import (
    compose_market_analysis_candidate,
)
from services.analysis.pre_entry_action_resolver import (
    resolve_pre_entry_market_action,
)
from services.certification.task9_live_decision_audit import (
    _disposition,
)
from test_market_analysis_candidate_composer import (
    composition,
    policy,
)


_NIFTY_RANKING_BLOCKER = (
    "DIRECTIONAL OPTION-CHAIN INTELLIGENCE IS REQUIRED "
    "FOR CONTRACT RANKING"
)

_SENSEX_RANKING_BLOCKER = (
    "CONFLICTING OPTION-CHAIN INTELLIGENCE DOES NOT "
    "PERMIT CONTRACT RANKING"
)


def _blocked_candidate(symbol):
    supplied = composition(symbol)

    if symbol == "NIFTY":
        option_chain = supplied.option_chain
        directional_bias = "NEUTRAL"
        ranking_blocker = _NIFTY_RANKING_BLOCKER
    else:
        bullish_metric = supplied.option_chain.metrics[0]
        bearish_metric = replace(
            bullish_metric,
            metric_name="PCR_VOLUME",
            value=0.8,
            signal="BEARISH",
        )

        option_chain = replace(
            supplied.option_chain,
            source_status="AVAILABLE",
            metrics=(
                bullish_metric,
                bearish_metric,
            ),
            intelligence_status="CONFLICTING",
            aggregate_bias="MIXED",
            aggregate_strength=0.05,
            bullish_metrics=(
                bullish_metric.metric_name,
            ),
            bearish_metrics=(
                bearish_metric.metric_name,
            ),
            neutral_metrics=(),
            unavailable_metrics=(),
            valid_metric_count=2,
            unavailable_metric_count=0,
            blockers=(),
            warnings=(
                "CONFLICTING OPTION-CHAIN INTELLIGENCE",
            ),
        )
        directional_bias = "MIXED"
        ranking_blocker = _SENSEX_RANKING_BLOCKER

    ranking = replace(
        supplied.option_contract_eligibility,
        directional_bias=directional_bias,
        required_option_type=None,
        ranking_status="BLOCKED",
        ranked_candidates=(),
        rejected_candidates=(),
        blockers=(ranking_blocker,),
        warnings=(),
        diagnostics=(),
    )

    candidate = compose_market_analysis_candidate(
        composition(
            symbol,
            option_chain=option_chain,
            option_contract_eligibility=ranking,
        ),
        policy("NEUTRAL"),
    )

    return candidate


@pytest.mark.parametrize(
    "symbol,expected_blockers,expected_eligibility",
    (
        (
            "NIFTY",
            ("OPTION_RANKING_BLOCKED",),
            "INELIGIBLE",
        ),
        (
            "SENSEX",
            (
                "OPTION_CHAIN_CONFLICTING",
                "OPTION_RANKING_BLOCKED",
            ),
            "UNAVAILABLE",
        ),
    ),
)
def test_policy_blocked_options_are_not_evidence_unavailable(
    symbol,
    expected_blockers,
    expected_eligibility,
):
    candidate = _blocked_candidate(symbol)

    assert candidate.eligibility == expected_eligibility
    assert candidate.direction == "UNAVAILABLE"
    assert candidate.confidence == 0.0
    assert candidate.score == 0.0

    for blocker in expected_blockers:
        assert blocker in candidate.blockers

    assert (
        "EVIDENCE_UNAVAILABLE_OPTION_CHAIN"
        not in candidate.blockers
    )
    assert (
        "EVIDENCE_UNAVAILABLE_OPTION_CONTRACT_ELIGIBILITY"
        not in candidate.blockers
    )


@pytest.mark.parametrize(
    "symbol,expected_reason",
    (
        ("NIFTY", "OPTION_RANKING_BLOCKED"),
        ("SENSEX", "OPTION_CHAIN_CONFLICTING"),
    ),
)
def test_policy_blocked_options_remain_no_trade_abstentions(
    symbol,
    expected_reason,
):
    candidate = _blocked_candidate(symbol)

    action = resolve_pre_entry_market_action(
        candidate=candidate,
        cycle_id=f"blocked-option-{symbol}",
        observation_id=f"blocked-option-observation-{symbol}",
        evaluated_at=candidate.received_at,
    )

    assert action.action == "NO_TRADE"
    assert action.selected_for_parent_comparison is False
    assert action.confidence == 0.0
    assert action.score == 0.0
    assert action.reasons == (expected_reason,)
    assert expected_reason in action.blockers
    assert (
        "REQUIRED_EVIDENCE_UNAVAILABLE"
        not in action.blockers
    )

    assert (
        _disposition(
            blockers=action.blockers,
            action=action.action,
            eligibility=action.candidate_eligibility,
        )
        == "POLICY_ABSTENTION"
    )
