"""B3 five-market descriptive comparison cannot rank or conceal unavailable data."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x9_ledger_v1 import NOW, ledger, result

from services.x7.contracts_v1 import MARKETS
from services.x8.regime_description_v1 import describe_x8_regime_evidence_v1
from services.x9.comparison_safeguards_v1 import audit_x9_comparison_safeguards_v1
from services.x9.research_eligibility_v1 import evaluate_x9_research_eligibility_v1
from services.x9.session_prerequisites_v1 import build_x9_session_matrix_v1


def make(*, delayed=None, reports=None, freshness=None, skew=15, shared=()):
    rows = tuple(
        result(
            m,
            NOW - timedelta(seconds=delayed) if m == "NATGASMINI" and delayed is not None else NOW,
        )
        for m in MARKETS
    )
    base = ledger(rows, skew=max(100, (delayed or 0) + 1))
    matrix = build_x9_session_matrix_v1(
        ledger=base,
        readiness=rows,
        reported_states=reports or tuple((m, "REPORTED_OPEN") for m in MARKETS),
    )
    descriptions = tuple(
        describe_x8_regime_evidence_v1(
            readiness=row,
            max_age_seconds=(freshness or {}).get(row.market, 60),
        )
        for row in rows
    )
    eligibility = evaluate_x9_research_eligibility_v1(
        ledger=base,
        session_matrix=matrix,
        readiness=rows,
        descriptions=descriptions,
    )
    return (
        audit_x9_comparison_safeguards_v1(
            ledger=base,
            eligibility=eligibility,
            max_capture_skew_seconds=skew,
            shared_source_warnings=shared,
        ),
        base,
        eligibility,
    )


def test_all_five_retained_and_never_ranked():
    row, _, _ = make()
    assert tuple(x[0] for x in row.per_market) == MARKETS
    assert row.ready_for_descriptive_comparison
    assert row.selected_market is None and row.rankings == ()


@pytest.mark.parametrize("market", MARKETS)
def test_closed_market_is_not_comparable(market):
    reports = tuple((m, "REPORTED_CLOSED" if m == market else "REPORTED_OPEN") for m in MARKETS)
    row, _, _ = make(reports=reports)
    assert row.per_market[MARKETS.index(market)][1] == "REPORTED_CLOSED"
    assert not row.ready_for_descriptive_comparison


@pytest.mark.parametrize("market", MARKETS)
def test_missing_freshness_prevents_five_market_comparison(market):
    row, _, _ = make(freshness={market: 5})
    assert row.per_market[MARKETS.index(market)][1] == "EVIDENCE_INCOMPLETE"
    assert not row.ready_for_descriptive_comparison


def test_x9_source_skew_is_descriptive_not_trading_authority():
    row, _, _ = make(delayed=10, skew=5)
    assert row.per_market[4][1] == "TIMING_SKEW"
    assert not row.ready_for_descriptive_comparison
    assert not row.execution_authority


def test_shared_source_warnings_are_normalized_and_explicit():
    row, _, _ = make(shared=("SHARED_PUBLISHER", "SAME_PRICE_SERIES", "SHARED_PUBLISHER"))
    assert row.shared_source_warnings == ("SAME_PRICE_SERIES", "SHARED_PUBLISHER")
    assert row.ready_for_descriptive_comparison


def test_wrong_ledger_rejected():
    _, base, eligibility = make()
    with pytest.raises(ValueError, match="different cycles"):
        audit_x9_comparison_safeguards_v1(
            ledger=replace(base, parent_cycle_id="DIFFERENT"),
            eligibility=eligibility,
            max_capture_skew_seconds=15,
        )


@pytest.mark.parametrize("bad", (0, -5, float("nan"), float("inf"), True, None))
def test_invalid_skew_limit_rejected(bad):
    _, base, eligibility = make()
    with pytest.raises(ValueError):
        audit_x9_comparison_safeguards_v1(
            ledger=base,
            eligibility=eligibility,
            max_capture_skew_seconds=bad,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("selected_market", "NIFTY"),
        ("rankings", ("NIFTY",)),
        ("independent_vote", True),
        ("risk_authority", True),
        ("capital_admission_allowed", True),
    ),
)
def test_cannot_promote_research_to_selection_or_authority(field, value):
    row, _, _ = make()
    if field == "capital_admission_allowed":
        assert not hasattr(row, field)
    else:
        with pytest.raises(ValueError):
            replace(row, **{field: value})


def test_recalculated_source_rejects_manually_forged_comparable_status():
    from services.x9.comparison_safeguards_v1 import validate_x9_comparison_safeguards_v1

    original, ledger_source, eligibility_source = make(delayed=10, skew=5)
    changed = replace(
        original,
        per_market=original.per_market[:4] + (("NATGASMINI", "COMPARABLE_CONTEXT", ()),),
        ready_for_descriptive_comparison=True,
    )
    with pytest.raises(ValueError, match="differs"):
        validate_x9_comparison_safeguards_v1(
            ledger=ledger_source,
            eligibility=eligibility_source,
            safeguards=changed,
        )
