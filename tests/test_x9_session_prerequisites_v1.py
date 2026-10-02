"""B1 session reports are descriptive and source-bound, never eligibility."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x9_ledger_v1 import NOW, ledger, result

from services.x7.contracts_v1 import MARKETS
from services.x8.readiness_v1 import build_x8_regime_readiness_v1
from services.x9.session_prerequisites_v1 import build_x9_session_matrix_v1


def make(readiness=None, reports=None):
    readiness = readiness or tuple(result(m) for m in MARKETS)
    reports = reports or tuple((m, "REPORTED_OPEN") for m in MARKETS)
    rows = ledger(readiness)
    return build_x9_session_matrix_v1(
        ledger=rows,
        readiness=readiness,
        reported_states=reports,
    )


def change_session(market, *, state="UNAVAILABLE", pit=False):
    row = result(market)
    refs = tuple(
        replace(
            ref,
            state=state,
            point_in_time_verified=pit,
            available_at=None if not pit else ref.available_at,
        )
        if ref.family == "MARKET_SESSION"
        else ref
        for ref in row.evidence
    )
    return build_x8_regime_readiness_v1(
        market=market,
        session_id=row.session_id,
        capture_id=row.capture_id,
        as_of=row.as_of,
        evidence=refs,
    )


def test_all_five_session_reports_ordered_and_not_ranked():
    matrix = make(reports=tuple((m, "REPORTED_OPEN") for m in reversed(MARKETS)))
    assert tuple(x.market for x in matrix.prerequisites) == MARKETS
    assert matrix.status == "COMPLETE_DESCRIPTIVE"
    assert matrix.reported_index_overlap
    assert matrix.selected_market is None and matrix.rankings == ()
    assert not matrix.execution_authority and not matrix.risk_authority


@pytest.mark.parametrize("market", MARKETS)
def test_closed_report_is_not_missing_data(market):
    states = tuple((m, "REPORTED_CLOSED" if m == market else "REPORTED_OPEN") for m in MARKETS)
    out = make(reports=states)
    assert out.prerequisites[MARKETS.index(market)].reported_state == "REPORTED_CLOSED"
    assert out.reported_index_overlap is (market not in ("NIFTY", "SENSEX"))


@pytest.mark.parametrize("market", MARKETS)
def test_missing_session_requires_explicit_unknown(market):
    readiness = tuple(change_session(m) if m == market else result(m) for m in MARKETS)
    with pytest.raises(ValueError, match="Unverified"):
        make(readiness=readiness)
    reports = tuple((m, "UNKNOWN" if m == market else "REPORTED_OPEN") for m in MARKETS)
    out = make(readiness=readiness, reports=reports)
    assert out.status == "INCOMPLETE_DESCRIPTIVE"
    assert out.prerequisites[MARKETS.index(market)].session_source_sha256 is None


@pytest.mark.parametrize("market", MARKETS)
def test_duplicate_or_absent_report_rejected(market):
    reports = tuple((m, "REPORTED_OPEN") for m in MARKETS if m != market)
    with pytest.raises(ValueError):
        make(reports=reports)
    reports = reports + (reports[0],)
    with pytest.raises(ValueError):
        make(reports=reports)


def test_wrong_readiness_hash_fails_closed():
    rows = tuple(result(m) for m in MARKETS)
    changed = replace(rows[0].evidence[0], source_sha256="a" * 63 + "b")
    altered = build_x8_regime_readiness_v1(
        market="NIFTY",
        session_id=rows[0].session_id,
        capture_id=rows[0].capture_id,
        as_of=NOW,
        evidence=(changed, *rows[0].evidence[1:]),
    )
    with pytest.raises(ValueError, match="does not match"):
        build_x9_session_matrix_v1(
            ledger=ledger(rows),
            readiness=(altered, *rows[1:]),
            reported_states=tuple((m, "REPORTED_OPEN") for m in MARKETS),
        )


def test_future_source_fails_at_x8_boundary():
    row = result("NIFTY")
    future = replace(
        row.evidence[0],
        observed_at=NOW + timedelta(seconds=1),
        available_at=NOW + timedelta(seconds=2),
    )
    with pytest.raises(ValueError, match="Future"):
        replace(row, evidence=(future, *row.evidence[1:]))


@pytest.mark.parametrize(
    "authority",
    ("execution_authority", "risk_authority", "certification_authority", "independent_vote"),
)
def test_session_matrix_cannot_acquire_authority(authority):
    with pytest.raises(ValueError):
        replace(make(), **{authority: True})


def test_constructor_cannot_forge_index_overlap():
    with pytest.raises(ValueError):
        replace(make(), reported_index_overlap=False)


def test_session_input_order_does_not_change_digest():
    states = tuple((m, "REPORTED_OPEN") for m in MARKETS)
    assert make(reports=states).sha256() == make(reports=tuple(reversed(states))).sha256()
