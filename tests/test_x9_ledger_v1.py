"""X9 Phase A coverage: complete five-market comparison without selecting."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from services.x7.contracts_v1 import MARKETS
from services.x8.contracts_v1 import X8EvidenceReferenceV1
from services.x8.readiness_v1 import build_x8_regime_readiness_v1
from services.x9.ledger_v1 import build_x9_five_market_ledger_v1

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)


def result(market, as_of=NOW, missing=False):
    families = ["TECHNICAL", "MARKET_SESSION", "DATA_QUALITY"] + (
        ["FUTURES"] if market not in ("NIFTY", "SENSEX") else []
    )
    if missing:
        families.remove("DATA_QUALITY")
    rows = tuple(
        X8EvidenceReferenceV1(
            f,
            f + "_SRC",
            f + "_ROW",
            "a" * 64,
            as_of - timedelta(seconds=20),
            as_of - timedelta(seconds=10),
            "AVAILABLE",
            True,
        )
        for f in families
    )
    return build_x8_regime_readiness_v1(
        market=market,
        session_id="S",
        capture_id="C",
        as_of=as_of,
        evidence=rows,
    )


def ledger(readiness=None, as_of=NOW, skew=5):
    if readiness is None:
        readiness = tuple(result(market) for market in MARKETS)
    return build_x9_five_market_ledger_v1(
        parent_cycle_id="CYCLE",
        as_of=as_of,
        readiness=readiness,
        max_skew_seconds=skew,
    )


def test_all_five_markets_are_explicit_unranked_slots():
    out = ledger()
    assert out.status == "COMPLETE_RESEARCH"
    assert tuple(x.market for x in out.slots) == MARKETS
    assert out.selected_market is None and out.rankings == ()
    assert all(s.regime_label == "UNASSESSED" and s.eligibility == "UNASSESSED" for s in out.slots)
    assert not out.execution_authority and not out.certification_authority


@pytest.mark.parametrize("missing", MARKETS)
def test_each_missing_market_rejected(missing):
    with pytest.raises(ValueError):
        ledger(tuple(result(m) for m in MARKETS if m != missing))


@pytest.mark.parametrize("market", MARKETS)
def test_each_market_can_remain_unavailable_with_rationale(market):
    inputs = tuple(result(m, missing=(m == market)) for m in MARKETS)
    out = ledger(inputs)
    assert out.status == "INCOMPLETE_RESEARCH"
    assert f"{market}_REGIME_READINESS_UNAVAILABLE" in out.blockers
    assert len(out.slots) == 5 and out.selected_market is None


@pytest.mark.parametrize("market", MARKETS)
def test_each_market_cannot_have_future_capture(market):
    inputs = tuple(result(m, NOW + timedelta(seconds=1) if m == market else NOW) for m in MARKETS)
    with pytest.raises(ValueError, match="Future"):
        ledger(inputs)


@pytest.mark.parametrize("market", MARKETS)
def test_each_market_cannot_exceed_skew(market):
    inputs = tuple(result(m, NOW - timedelta(seconds=6) if m == market else NOW) for m in MARKETS)
    with pytest.raises(ValueError, match="skew"):
        ledger(inputs)


def test_sorting_does_not_depend_on_provider_order():
    inputs = tuple(result(m) for m in MARKETS)
    assert ledger(inputs).sha256() == ledger(tuple(reversed(inputs))).sha256()


def test_duplicate_market_rejected_even_when_count_is_five():
    inputs = tuple(result(m) for m in MARKETS)
    with pytest.raises(ValueError):
        ledger(inputs[:-1] + (inputs[0],))


@pytest.mark.parametrize("bad_skew", [-1, float("nan"), float("inf"), True, None, "5"])
def test_invalid_skew_policy_rejected(bad_skew):
    with pytest.raises(ValueError):
        ledger(skew=bad_skew)


@pytest.mark.parametrize(
    "name,value",
    [
        ("selected_market", "NIFTY"),
        ("rankings", ("NIFTY",)),
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("independent_vote", True),
    ],
)
def test_x9_cannot_select_rank_or_gain_authority(name, value):
    with pytest.raises(ValueError):
        replace(ledger(), **{name: value})


def test_only_exact_cycle_identity_is_admissible():
    with pytest.raises(ValueError):
        build_x9_five_market_ledger_v1(
            parent_cycle_id=" ",
            as_of=NOW,
            readiness=tuple(result(m) for m in MARKETS),
            max_skew_seconds=5,
        )


def test_cannot_upgrade_incomplete_ledger_by_replace():
    inputs = tuple(result(m, missing=(m == "GOLDM")) for m in MARKETS)
    with pytest.raises(ValueError):
        replace(ledger(inputs), status="COMPLETE_RESEARCH")


def test_cannot_forge_timing_skew():
    with pytest.raises(ValueError):
        replace(ledger(), timing_skew_seconds=100.0)
