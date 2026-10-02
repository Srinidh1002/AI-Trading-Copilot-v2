"""X10 Phase A coverage: supplied portfolio facts never become risk authority."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from services.x7.contracts_v1 import MARKETS
from services.x8.contracts_v1 import X8EvidenceReferenceV1
from services.x8.readiness_v1 import build_x8_regime_readiness_v1
from services.x9.ledger_v1 import build_x9_five_market_ledger_v1
from services.x10.contracts_v1 import X10MarketExposureReferenceV1
from services.x10.readiness_v1 import build_x10_portfolio_readiness_v1

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)


def ledger():
    rows = []
    for market in MARKETS:
        families = ["TECHNICAL", "MARKET_SESSION", "DATA_QUALITY"] + (
            ["FUTURES"] if market not in ("NIFTY", "SENSEX") else []
        )
        evidence = tuple(
            X8EvidenceReferenceV1(
                family,
                family + "_SRC",
                family + "_REC",
                "f" * 64,
                NOW - timedelta(seconds=20),
                NOW - timedelta(seconds=10),
                "AVAILABLE",
                True,
            )
            for family in families
        )
        rows.append(
            build_x8_regime_readiness_v1(
                market=market,
                session_id="S",
                capture_id="C",
                as_of=NOW,
                evidence=evidence,
            )
        )
    return build_x9_five_market_ledger_v1(
        parent_cycle_id="PARENT",
        as_of=NOW,
        readiness=tuple(rows),
        max_skew_seconds=2,
    )


def exposure(market, state="REPORTED"):
    return X10MarketExposureReferenceV1(
        market=market,
        source_kind="P8_PAPER_REFERENCE" if market in ("NIFTY", "SENSEX") else "EXTERNAL_RESEARCH",
        source_id="SRC_" + market,
        source_record_id="ROW_" + market,
        source_sha256="a" * 64,
        observed_at=NOW - timedelta(seconds=20),
        available_at=NOW - timedelta(seconds=10) if state == "REPORTED" else None,
        state=state,
        source_verified=(state == "REPORTED"),
        open_position_count=1 if state == "REPORTED" else None,
        pending_reservation_count=0 if state == "REPORTED" else None,
    )


def batch(records=None):
    return build_x10_portfolio_readiness_v1(
        ledger=ledger(),
        references=tuple(exposure(m) for m in MARKETS) if records is None else records,
    )


def test_all_five_reported_counts_are_still_only_read_only_research():
    result = batch()
    assert result.status == "COMPLETE_RESEARCH"
    assert result.total_open_positions == 5
    assert result.total_pending_reservations == 0
    assert result.deployable_capital is None and result.risk_budget is None
    assert result.capital_admission_allowed is False
    assert result.execution_authority is False and result.risk_authority is False
    assert result.position_authority is False and result.certification_authority is False


@pytest.mark.parametrize("market", MARKETS)
def test_each_missing_market_is_explicitly_unknown_not_zero(market):
    records = tuple(
        exposure(m)
        if m != market
        else replace(
            exposure(m),
            state="UNAVAILABLE",
            source_verified=False,
            open_position_count=None,
            pending_reservation_count=None,
            available_at=None,
        )
        for m in MARKETS
    )
    result = batch(records)
    assert result.status == "INCOMPLETE_RESEARCH"
    assert result.total_open_positions is None
    assert f"{market}_EXPOSURE_UNAVAILABLE" in result.blockers


@pytest.mark.parametrize("market", MARKETS)
def test_future_available_at_rejected_for_every_market(market):
    records = tuple(
        replace(exposure(m), available_at=NOW + timedelta(seconds=1))
        if m == market
        else exposure(m)
        for m in MARKETS
    )
    with pytest.raises(ValueError, match="not known"):
        batch(records)


@pytest.mark.parametrize("market", MARKETS)
def test_duplicate_market_rejected(market):
    records = tuple(exposure(m) for m in MARKETS)
    ix = MARKETS.index(market)
    clone = records[:ix] + (records[0],) + records[ix + 1 :]
    if market == MARKETS[0]:
        clone = records[:-1] + (records[0],)
    with pytest.raises(ValueError):
        batch(clone)


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI"))
def test_p8_cannot_implicitly_authorize_mcx_exposure(market):
    with pytest.raises(ValueError, match="MCX"):
        replace(exposure(market), source_kind="P8_PAPER_REFERENCE")


def test_shared_source_cannot_be_summed_twice():
    rows = tuple(exposure(m) for m in MARKETS)
    shared = replace(
        rows[1],
        source_id=rows[0].source_id,
        source_record_id=rows[0].source_record_id,
    )
    result = batch((rows[0], shared, *rows[2:]))
    assert result.shared_source_groups == (("NIFTY", "SENSEX"),)
    assert result.total_open_positions is None
    assert result.total_pending_reservations is None


def test_deterministic_order_and_digest():
    records = tuple(exposure(m) for m in MARKETS)
    assert batch(records).sha256() == batch(tuple(reversed(records))).sha256()


@pytest.mark.parametrize(
    "name,value",
    [
        ("deployable_capital", 1000.0),
        ("risk_budget", 500.0),
        ("capital_admission_allowed", True),
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("independent_vote", True),
    ],
)
def test_x10_cannot_grant_capital_or_execution_authority(name, value):
    with pytest.raises(ValueError):
        replace(batch(), **{name: value})


@pytest.mark.parametrize("bad", [-1, 1.5, True, "0"])
def test_count_type_is_strict(bad):
    with pytest.raises(ValueError):
        replace(exposure("NIFTY"), open_position_count=bad)


def test_missing_source_cannot_claim_reported_positions():
    with pytest.raises(ValueError):
        replace(exposure("NIFTY"), source_kind="NONE")


def test_research_cannot_manufacture_any_p8_balance():
    result = batch()
    assert result.deployable_capital is None
    assert result.risk_budget is None
    assert all(x.state == "REPORTED" for x in result.references)
    assert len([x for x in result.warnings if "EXTERNAL_RESEARCH" in x]) == 3


def test_cannot_forge_portfolio_totals():
    with pytest.raises(ValueError):
        replace(batch(), total_open_positions=0)


def test_cannot_claim_complete_with_missing_exposure():
    rows = tuple(
        exposure(m)
        if m != "GOLDM"
        else replace(
            exposure(m),
            state="UNAVAILABLE",
            source_verified=False,
            open_position_count=None,
            pending_reservation_count=None,
            available_at=None,
        )
        for m in MARKETS
    )
    with pytest.raises(ValueError):
        replace(batch(rows), status="COMPLETE_RESEARCH")
