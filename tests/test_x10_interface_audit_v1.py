"""B1 ownership inventory has no P7/P8 authority or MCX certification."""

from dataclasses import replace

import pytest
from test_x10_readiness_v1 import exposure, ledger

from services.x7.contracts_v1 import MARKETS
from services.x10.interface_audit_v1 import audit_x10_interfaces_v1
from services.x10.readiness_v1 import build_x10_portfolio_readiness_v1


def build(rows=None):
    parent = ledger()
    readiness = build_x10_portfolio_readiness_v1(
        ledger=parent,
        references=rows or tuple(exposure(m) for m in MARKETS),
    )
    return audit_x10_interfaces_v1(ledger=parent, readiness=readiness)


def test_five_market_coverage_does_not_certify_any_adapter():
    out = build()
    assert tuple(row.market for row in out.coverage) == MARKETS
    assert out.verified_adapters == 0
    assert not out.portfolio_authority and not out.capital_admission_allowed
    assert all(not row.verified_runtime_adapter for row in out.coverage)
    assert not out.execution_authority and not out.certification_authority


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI"))
def test_mcx_p8_is_not_implicitly_verified(market):
    out = build()
    row = out.coverage[MARKETS.index(market)]
    assert row.p8_portfolio_interface == "MCX_UNVERIFIED"
    with pytest.raises(ValueError):
        replace(row, p8_portfolio_interface="INDEX_CONTRACT_REFERENCE_ONLY")


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_index_contract_reference_is_not_a_runtime_adapter(market):
    row = build().coverage[MARKETS.index(market)]
    assert row.p8_portfolio_interface == "INDEX_CONTRACT_REFERENCE_ONLY"
    with pytest.raises(ValueError):
        replace(row, verified_runtime_adapter=True)


@pytest.mark.parametrize("market", MARKETS)
def test_none_of_five_p7_interfaces_authorizes_a_position(market):
    row = build().coverage[MARKETS.index(market)]
    assert row.p7_position_interface == "CONTRACT_REFERENCE_ONLY"
    assert row.p7_recovery_interface == "CONTRACT_REFERENCE_ONLY"
    with pytest.raises(ValueError):
        replace(row, p7_position_interface="RUNTIME_VERIFIED")


@pytest.mark.parametrize(
    "field",
    (
        "portfolio_authority",
        "capital_admission_allowed",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ),
)
def test_no_authority_can_be_added_by_constructor(field):
    with pytest.raises(ValueError):
        replace(build(), **{field: True})


def test_wrong_x9_link_rejected():
    parent = ledger()
    readiness = build_x10_portfolio_readiness_v1(
        ledger=parent,
        references=tuple(exposure(m) for m in MARKETS),
    )
    with pytest.raises(ValueError, match="not bound"):
        audit_x10_interfaces_v1(
            ledger=parent,
            readiness=replace(readiness, x9_ledger_sha256="a" * 64),
        )


def test_audit_is_deterministic_without_network_or_provider_calls():
    assert build().sha256() == build().sha256()


def test_cannot_upgrade_audit_when_exposure_incomplete():
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
    out = build(rows)
    assert out.verified_adapters == 0
    assert out.coverage[3].p8_portfolio_interface == "MCX_UNVERIFIED"
