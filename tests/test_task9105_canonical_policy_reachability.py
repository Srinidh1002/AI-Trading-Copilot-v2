"""Provider-free reachability controls for Task 9 canonical policy families."""
from services.analysis.canonical_directional_policy_evaluator import (
    evaluate_canonical_directional_policy,
)
from services.analysis.canonical_evidence_family_adapters import (
    broader_market_family,
    derivatives_family,
    regime_family,
    technical_family,
)
from services.contracts.canonical_evidence_family_v1 import (
    CanonicalEvidenceFamilySetV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from tests.fixtures.p5_12 import (
    REPLAY_EVALUATED_AT,
    STRONG_BEARISH,
    WEAK_BEARISH,
    build_broader_market_intelligence,
    build_market_regime,
    build_option_chain_intelligence,
    build_technical_intelligence,
)


IDENTITY = ("NIFTY", "NSE")


def _conflicting_derivatives():
    """A healthy captured chain whose canonical aggregate is conflicting."""
    base = build_option_chain_intelligence(IDENTITY, STRONG_BEARISH)
    return build_option_chain_intelligence(
        IDENTITY,
        STRONG_BEARISH,
        overrides={
            "intelligence_status": "CONFLICTING",
            "aggregate_bias": "MIXED",
            "metrics": base.metrics + (
                OptionChainMetricV1("OI_BUILDUP", 1.0, "BULLISH", "VALID", 10),
            ),
            "bullish_metrics": ("OI_BUILDUP",),
            "bearish_metrics": ("PCR_OPEN_INTEREST",),
            "valid_metric_count": 2,
            "blockers": ("OPTION_CHAIN_CONFLICTING",),
        },
    )


def _family_set(*, technical, derivatives=None, regime=None, broader=None):
    values = [technical_family(technical)]
    if derivatives is not None:
        values.append(derivatives_family(derivatives))
    if regime is not None:
        values.append(regime_family(regime))
    if broader is not None:
        values.append(broader_market_family(broader))
    return CanonicalEvidenceFamilySetV1(tuple(values))


def _policy(families):
    return evaluate_canonical_directional_policy(
        policy_id="task9105-reachability",
        symbol="NIFTY",
        exchange="NSE",
        evaluated_at=REPLAY_EVALUATED_AT,
        evidence=families,
    )


def _directional(families):
    return tuple(
        item for item in families.contributions
        if item.status == "AVAILABLE"
        and item.role in {"DIRECTIONAL", "CONFIRMATION", "CONTRADICTION"}
        and item.direction in {"BULLISH", "BEARISH"}
    )


def test_strong_aligned_production_adapters_reach_trade_with_exactly_two_families():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, STRONG_BEARISH),
        derivatives=build_option_chain_intelligence(IDENTITY, STRONG_BEARISH),
        regime=build_market_regime(IDENTITY, STRONG_BEARISH),
        broader=build_broader_market_intelligence(IDENTITY, STRONG_BEARISH),
    )
    result = _policy(families)

    technical, derivatives = families.contributions[:2]
    assert (technical.status, technical.direction) == ("AVAILABLE", "BEARISH")
    assert (derivatives.status, derivatives.direction) == ("AVAILABLE", "BEARISH")
    assert tuple(item.family for item in _directional(families)) == ("TECHNICAL", "DERIVATIVES")
    assert result.direction == "BEARISH"
    assert result.confidence > 55
    assert result.decision == "TRADE"
    assert not result.blockers


def test_weak_aligned_families_reach_count_but_fail_real_confidence_gate():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, WEAK_BEARISH),
        derivatives=build_option_chain_intelligence(IDENTITY, WEAK_BEARISH),
    )
    result = _policy(families)

    assert len(_directional(families)) == 2
    assert result.confidence < 55
    assert result.decision == "NO_TRADE"


def test_conflicting_derivatives_cannot_be_replaced_by_option_submetrics():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, STRONG_BEARISH),
        derivatives=_conflicting_derivatives(),
    )
    result = _policy(families)

    derivatives = next(item for item in families.contributions if item.family == "DERIVATIVES")
    assert (derivatives.status, derivatives.direction) == ("UNAVAILABLE", "UNAVAILABLE")
    assert tuple(item.family for item in _directional(families)) == ("TECHNICAL",)
    assert result.decision == "NO_TRADE"


def test_regime_cannot_supply_the_second_directional_vote():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, STRONG_BEARISH),
        regime=build_market_regime(IDENTITY, STRONG_BEARISH),
    )
    result = _policy(families)

    regime = next(item for item in families.contributions if item.family == "REGIME")
    assert (regime.role, regime.direction) == ("CONFIRMATION", "NEUTRAL")
    assert len(_directional(families)) == 1
    assert result.decision == "NO_TRADE"


def test_broader_market_cannot_supply_the_second_directional_vote():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, STRONG_BEARISH),
        broader=build_broader_market_intelligence(IDENTITY, STRONG_BEARISH),
    )
    result = _policy(families)

    broader = next(item for item in families.contributions if item.family == "BROADER_MARKET")
    assert (broader.role, broader.direction, broader.strength) == ("CONFIRMATION", "NEUTRAL", 0)
    assert len(_directional(families)) == 1
    assert result.decision == "NO_TRADE"


def test_unavailable_derivatives_and_grouped_evidence_cannot_inflate_family_count():
    families = _family_set(
        technical=build_technical_intelligence(IDENTITY, STRONG_BEARISH),
        derivatives=_conflicting_derivatives(),
    )
    result = _policy(families)

    # The production family set has no grouped-pillar input at all: grouped
    # technical/options/ranking records are intentionally outside this vote.
    assert tuple(item.family for item in families.contributions) == ("TECHNICAL", "DERIVATIVES")
    assert len(_directional(families)) == 1
    assert result.decision == "NO_TRADE"
