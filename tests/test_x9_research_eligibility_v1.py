"""B2 five-market research comparability; no trading eligibility."""

from dataclasses import replace

import pytest
from test_x9_ledger_v1 import ledger, result

from services.x7.contracts_v1 import MARKETS
from services.x8.regime_description_v1 import describe_x8_regime_evidence_v1
from services.x9.research_eligibility_v1 import evaluate_x9_research_eligibility_v1
from services.x9.session_prerequisites_v1 import build_x9_session_matrix_v1


def build(*, reports=None, sources=None, budgets=None):
    sources = sources or tuple(result(m) for m in MARKETS)
    original = ledger(sources)
    reports = reports or tuple((m, "REPORTED_OPEN") for m in MARKETS)
    matrix = build_x9_session_matrix_v1(
        ledger=original,
        readiness=sources,
        reported_states=reports,
    )
    budgets = budgets or {}
    diagnostics = tuple(
        describe_x8_regime_evidence_v1(
            readiness=source,
            max_age_seconds=budgets.get(source.market, 60),
        )
        for source in sources
    )
    return evaluate_x9_research_eligibility_v1(
        ledger=original,
        session_matrix=matrix,
        readiness=sources,
        descriptions=diagnostics,
    )


def test_five_complete_descriptive_slots_not_trade_ranking():
    out = build()
    assert tuple(x.market for x in out.candidates) == MARKETS
    assert out.comparable_market_count == 5
    assert out.descriptive_status == "COMPLETE_DESCRIPTIVE"
    assert out.selected_market is None and out.rankings == ()
    assert not out.independent_vote and not out.risk_authority
    assert out.sha256() == build().sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_reported_closed_is_not_current_comparable_context(market):
    out = build(
        reports=tuple((m, "REPORTED_CLOSED" if m == market else "REPORTED_OPEN") for m in MARKETS)
    )
    assert out.candidates[MARKETS.index(market)].status == "REPORTED_CLOSED"
    assert out.comparable_market_count == 4
    assert out.selected_market is None


@pytest.mark.parametrize("market", MARKETS)
def test_unusable_data_is_not_comparable_even_with_open_session(market):
    out = build(budgets={market: 5})
    assert out.candidates[MARKETS.index(market)].status == "EVIDENCE_INCOMPLETE"
    assert out.comparable_market_count == 4
    assert out.descriptive_status == "PARTIAL_DESCRIPTIVE"


@pytest.mark.parametrize("market", MARKETS)
def test_input_order_does_not_change_digest(market):
    sources = tuple(result(m) for m in MARKETS)
    assert build(sources=sources).sha256() == build(sources=tuple(reversed(sources))).sha256()


def test_unknown_session_requires_original_unverified_session():
    sources = tuple(result(m) for m in MARKETS)
    # The caller may conservatively mark a verified session unknown.
    reports = tuple((m, "UNKNOWN" if m == "GOLDM" else "REPORTED_OPEN") for m in MARKETS)
    out = build(sources=sources, reports=reports)
    assert out.candidates[MARKETS.index("GOLDM")].status == "SESSION_UNKNOWN"
    assert out.comparable_market_count == 4


def test_wrong_ledger_link_is_rejected():
    sources = tuple(result(m) for m in MARKETS)
    original = ledger(sources)
    matrix = build_x9_session_matrix_v1(
        ledger=original,
        readiness=sources,
        reported_states=tuple((m, "REPORTED_OPEN") for m in MARKETS),
    )
    diagnostics = tuple(
        describe_x8_regime_evidence_v1(
            readiness=s,
            max_age_seconds=60,
        )
        for s in sources
    )
    with pytest.raises(ValueError):
        evaluate_x9_research_eligibility_v1(
            ledger=original,
            session_matrix=replace(matrix, x9_ledger_sha256="f" * 64),
            readiness=sources,
            descriptions=diagnostics,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("selected_market", "NIFTY"),
        ("rankings", ("NIFTY",)),
        ("comparable_market_count", 99),
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("independent_vote", True),
        ("live_execution_eligible", True),
        ("schema_version", "V2"),
    ),
)
def test_no_invented_ranking_count_or_authority(field, value):
    with pytest.raises(ValueError):
        replace(build(), **{field: value})


def test_cannot_forge_individual_eligibility():
    original = build(
        reports=tuple((m, "REPORTED_CLOSED" if m == "GOLDM" else "REPORTED_OPEN") for m in MARKETS)
    )
    candidate = original.candidates[3]
    with pytest.raises(ValueError):
        replace(candidate, status="COMPARABLE_CONTEXT")


def test_duplicate_market_description_rejected():
    sources = tuple(result(m) for m in MARKETS)
    original = ledger(sources)
    matrix = build_x9_session_matrix_v1(
        ledger=original,
        readiness=sources,
        reported_states=tuple((m, "REPORTED_OPEN") for m in MARKETS),
    )
    descriptions = tuple(
        describe_x8_regime_evidence_v1(
            readiness=s,
            max_age_seconds=60,
        )
        for s in sources
    )
    with pytest.raises(ValueError):
        evaluate_x9_research_eligibility_v1(
            ledger=original,
            session_matrix=matrix,
            readiness=sources,
            descriptions=(descriptions[0], descriptions[0], *descriptions[2:]),
        )
