"""B2 descriptive freshness: no regime/prediction promotion."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x8_readiness_v1 import NOW, ready, ref

from services.x7.contracts_v1 import MARKETS
from services.x8.readiness_v1 import build_x8_regime_readiness_v1
from services.x8.regime_description_v1 import (
    describe_x8_regime_evidence_v1,
    validate_x8_regime_description_v1,
)


def make(market="NIFTY", **kw):
    return describe_x8_regime_evidence_v1(
        readiness=ready(market), max_age_seconds=kw.get("budget", 60)
    )


@pytest.mark.parametrize("market", MARKETS)
def test_five_markets_ready_only_for_future_classification(market):
    source = ready(market)
    row = describe_x8_regime_evidence_v1(readiness=source, max_age_seconds=60)
    validate_x8_regime_description_v1(readiness=source, description=row)
    assert row.research_status == "READY_FOR_CLASSIFICATION"
    assert row.regime_label == row.direction == row.volatility_regime == "UNASSESSED"
    assert not row.independent_vote and not row.execution_authority
    assert row.sha256() == row.sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_age_budget_downgrades_required_not_source(market):
    source = ready(market)
    row = describe_x8_regime_evidence_v1(readiness=source, max_age_seconds=5)
    assert row.research_status == "UNAVAILABLE"
    assert all(x[3] == "STALE" for x in row.family_diagnostics)
    assert source.status == "READY" and row.unusable_required_families


@pytest.mark.parametrize("market", MARKETS)
def test_optional_age_budget_reduces_completeness(market):
    original = ready(market, (ref("OPTIONS"),))
    evidence = tuple(
        replace(
            x, observed_at=NOW - timedelta(seconds=45), available_at=NOW - timedelta(seconds=10)
        )
        if x.family == "OPTIONS"
        else x
        for x in original.evidence
    )
    source = build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=evidence,
    )
    out = describe_x8_regime_evidence_v1(readiness=source, max_age_seconds=30)
    assert out.research_status == "PARTIAL"
    assert out.unusable_required_families == ()
    assert out.family_diagnostics[-1][3] == "STALE" or any(
        x[0] == "OPTIONS" and x[3] == "STALE" for x in out.family_diagnostics
    )


@pytest.mark.parametrize("state", ("PARTIAL", "UNVERIFIED", "STALE", "UNAVAILABLE"))
def test_required_nonusable_classified(state):
    base = ready()
    refs = tuple(
        replace(row, state=state, point_in_time_verified=False, available_at=None)
        if row.family == "TECHNICAL"
        else row
        for row in base.evidence
    )
    changed = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=refs,
    )
    out = describe_x8_regime_evidence_v1(readiness=changed, max_age_seconds=60)
    assert out.research_status == "UNAVAILABLE"
    assert "TECHNICAL" in out.unusable_required_families


@pytest.mark.parametrize("budget", (0, -5, float("nan"), float("inf"), "30", True, None))
def test_invalid_budget_fails_closed(budget):
    with pytest.raises(ValueError):
        describe_x8_regime_evidence_v1(readiness=ready(), max_age_seconds=budget)


def test_missing_required_fails_closed():
    row = ready()
    changed = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=tuple(ref for ref in row.evidence if ref.family != "TECHNICAL"),
    )
    out = describe_x8_regime_evidence_v1(readiness=changed, max_age_seconds=60)
    assert out.research_status == "UNAVAILABLE"
    assert out.unusable_required_families == ("TECHNICAL",)


@pytest.mark.parametrize(
    "field,value",
    (
        ("regime_label", "TRENDING_BULLISH"),
        ("direction", "BULLISH"),
        ("volatility_regime", "HIGH"),
        ("execution_authority", True),
        ("independent_vote", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("schema_version", "v2"),
    ),
)
def test_no_authority_or_classification_by_constructor(field, value):
    with pytest.raises(ValueError):
        replace(make(), **{field: value})


def test_status_cannot_be_directly_upgraded():
    source = ready()
    out = describe_x8_regime_evidence_v1(readiness=source, max_age_seconds=5)
    with pytest.raises(ValueError):
        replace(out, research_status="READY_FOR_CLASSIFICATION")


def test_original_source_hash_change_detected():
    source = ready()
    out = describe_x8_regime_evidence_v1(readiness=source, max_age_seconds=60)
    altered = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=(replace(source.evidence[0], source_sha256="1" * 64), *source.evidence[1:]),
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_x8_regime_description_v1(readiness=altered, description=out)


def test_wrong_original_type_fails_closed():
    with pytest.raises(TypeError):
        describe_x8_regime_evidence_v1(readiness=None, max_age_seconds=60)
