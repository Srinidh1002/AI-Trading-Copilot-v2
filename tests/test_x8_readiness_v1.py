"""X8 Phase A coverage: five-market source binding and readiness only."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from services.x7.contracts_v1 import MARKETS
from services.x8.contracts_v1 import X8EvidenceReferenceV1
from services.x8.readiness_v1 import build_x8_regime_readiness_v1

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
HASH = "a" * 64


def ref(family, status="AVAILABLE", **kwargs):
    return X8EvidenceReferenceV1(
        family,
        "SRC_" + family,
        "ROW_" + family,
        HASH,
        NOW - timedelta(seconds=20),
        NOW - timedelta(seconds=10) if status == "AVAILABLE" else None,
        status,
        status == "AVAILABLE",
        **kwargs,
    )


def ready(market="NIFTY", extra=()):
    families = ["TECHNICAL", "MARKET_SESSION", "DATA_QUALITY"]
    if market not in ("NIFTY", "SENSEX"):
        families.append("FUTURES")
    return build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=tuple(ref(f) for f in families) + extra,
    )


@pytest.mark.parametrize("market", MARKETS)
def test_five_market_ready_evidence_is_not_regime_label(market):
    result = ready(market)
    assert result.status == "READY"
    assert result.regime_label == "UNASSESSED"
    assert result.market == market and result.sha256() == result.sha256()
    assert not result.independent_vote and not result.execution_authority
    assert not result.risk_authority and not result.position_authority
    assert not result.certification_authority and not result.live_execution_eligible


@pytest.mark.parametrize("market", MARKETS)
def test_missing_technical_never_ready(market):
    row = ready(market)
    evidence = tuple(x for x in row.evidence if x.family != "TECHNICAL")
    result = build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=evidence,
    )
    assert result.status == "UNAVAILABLE"
    assert "REQUIRED_TECHNICAL_MISSING" in result.blockers


@pytest.mark.parametrize("market", MARKETS)
def test_optional_unverified_remains_partial(market):
    result = ready(market, (ref("EXTERNAL_CONTEXT", "UNVERIFIED"),))
    assert result.status == "PARTIAL"
    assert "OPTIONAL_EXTERNAL_CONTEXT_UNVERIFIED" in result.warnings


@pytest.mark.parametrize("market", MARKETS)
def test_hash_independent_of_supplied_evidence_order(market):
    record = ready(market)
    reordered = build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=tuple(reversed(record.evidence)),
    )
    assert record.sha256() == reordered.sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_unavailable_required_has_no_regime_claim(market):
    required = ready(market)
    rows = tuple(
        replace(row, state="STALE", available_at=None, point_in_time_verified=False)
        if row.family == "MARKET_SESSION"
        else row
        for row in required.evidence
    )
    result = build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=rows,
    )
    assert result.status == "UNAVAILABLE" and result.regime_label == "UNASSESSED"


@pytest.mark.parametrize(
    "family",
    [
        "TECHNICAL",
        "BREADTH",
        "FUTURES",
        "OPTIONS",
        "VOLATILITY",
        "EXTERNAL_CONTEXT",
        "MARKET_SESSION",
        "DATA_QUALITY",
    ],
)
def test_each_family_provenance_and_dependency(family):
    row = ref(family)
    assert len(row.sha256()) == 64
    assert row.source_record_id == "ROW_" + family


def test_options_and_futures_share_derivatives_dependency():
    result = ready("CRUDEOILM", (ref("OPTIONS"),))
    assert ("DERIVATIVES_POSITIONING", ("FUTURES", "OPTIONS")) in result.dependency_groups


def test_duplicate_family_fails():
    with pytest.raises(ValueError, match="Duplicate"):
        ready(extra=(ref("TECHNICAL"),))


def test_duplicate_source_record_across_families_fails():
    extra = replace(ref("BREADTH"), source_id="SRC_TECHNICAL", source_record_id="ROW_TECHNICAL")
    with pytest.raises(ValueError, match="Same source"):
        ready(extra=(extra,))


def test_future_available_time_fails():
    extra = replace(ref("BREADTH"), available_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="not available"):
        ready(extra=(extra,))


def test_future_observed_time_fails():
    extra = replace(
        ref("BREADTH"),
        observed_at=NOW + timedelta(seconds=1),
        available_at=NOW + timedelta(seconds=2),
    )
    with pytest.raises(ValueError, match="not available"):
        ready(extra=(extra,))


@pytest.mark.parametrize("bad", ["0" * 63, "Z" * 64, "garbage"])
def test_bad_source_hash_fails(bad):
    with pytest.raises(ValueError):
        replace(ref("BREADTH"), source_sha256=bad)


@pytest.mark.parametrize("value", [False, 1, "yes", None])
def test_invalid_pit_status_fails(value):
    with pytest.raises(ValueError):
        replace(ref("BREADTH"), point_in_time_verified=value)


@pytest.mark.parametrize(
    "name",
    [
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ],
)
def test_cannot_gain_any_authority(name):
    with pytest.raises(ValueError):
        replace(ref("TECHNICAL"), **{name: True})


@pytest.mark.parametrize("market", ["BANKNIFTY", "FINNIFTY", "", "CRUDEOIL"])
def test_market_scope_is_exactly_five(market):
    with pytest.raises(ValueError):
        ready(market)


def test_rejects_unsupported_regime_claim():
    with pytest.raises(ValueError):
        replace(ready(), regime_label="TRENDING_BULLISH")


def test_rejects_manual_status_upgrade():
    with pytest.raises(ValueError):
        replace(ready(), status="ELIGIBLE")


def test_cannot_upgrade_missing_to_ready_via_direct_replacement():
    baseline = ready()
    missing = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=tuple(row for row in baseline.evidence if row.family != "TECHNICAL"),
    )
    with pytest.raises(ValueError):
        replace(missing, status="READY")


def test_cannot_delete_required_blocker():
    baseline = ready()
    missing = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id="S",
        capture_id="C",
        as_of=NOW,
        evidence=tuple(row for row in baseline.evidence if row.family != "TECHNICAL"),
    )
    with pytest.raises(ValueError):
        replace(missing, blockers=())
