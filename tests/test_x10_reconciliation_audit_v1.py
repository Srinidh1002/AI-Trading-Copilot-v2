"""B3 replays B2 against original supplied P7/P8, using explicit test doubles.

Genuine canonical P7/P8 types must be exercised in the user's full worktree.
"""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x10_readiness_v1 import NOW, ledger
from test_x10_typed_projection_v1 import FakeP7, FakeP8, p7, p8, position

from services.x10 import typed_projection_v1 as source_module
from services.x10.reconciliation_audit_v1 import audit_x10_reconciliation_v1
from services.x10.typed_projection_v1 import project_x10_typed_portfolio_v1


@pytest.fixture(autouse=True)
def exact_test_doubles(monkeypatch):
    monkeypatch.setattr(source_module, "_p8_cls", lambda: FakeP8)
    monkeypatch.setattr(source_module, "_p7_cls", lambda: FakeP7)


def case(*, snapshot=None, records=(), missing=False):
    parent = ledger()
    if missing:
        args = dict(
            ledger=parent,
            p8_snapshot=None,
            expected_p8_sha256=None,
            p8_available_at=None,
            p7_snapshots=(),
            expected_p7_hashes=(),
        )
    else:
        snapshot = snapshot if snapshot is not None else p8()
        args = dict(
            ledger=parent,
            p8_snapshot=snapshot,
            expected_p8_sha256=snapshot.integrity_hash,
            p8_available_at=NOW - timedelta(seconds=2),
            p7_snapshots=records,
            expected_p7_hashes=tuple((r.paper_trade_id, r.integrity_hash) for r in records),
        )
    projected = project_x10_typed_portfolio_v1(**args)
    return projected, args


def audit(projected, args, **kw):
    original = dict(args)
    original.update(kw)
    return audit_x10_reconciliation_v1(
        projection=projected,
        expected_projection_sha256=projected.sha256(),
        **original,
    )


def test_missing_p8_remains_unavailable_not_zero():
    row, args = case(missing=True)
    out = audit(row, args)
    assert "P8_STATE_UNAVAILABLE_NOT_ZERO" in out.findings
    assert out.unresolved_capital_allocation
    assert out.verified_p7_record_count == 0


def test_empty_p8_keeps_mcx_unverified_and_no_capital_authority():
    row, args = case()
    out = audit(row, args)
    assert out.market_statuses[2:] == (
        ("CRUDEOILM", "MCX_UNVERIFIED"),
        ("GOLDM", "MCX_UNVERIFIED"),
        ("NATGASMINI", "MCX_UNVERIFIED"),
    )
    assert out.deployable_capital is None and not out.capital_admission_allowed
    assert "P7_P8_RECONCILIATION_NOT_PROVEN" in out.findings


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_matched_p7_p8_replays_original_identities(market):
    item = position(market)
    row, args = case(snapshot=p8(positions=(item,)), records=(p7(item),))
    out = audit(row, args)
    assert out.position_reconciliation == "P7_P8_MATCHED"
    assert out.verified_p7_record_count == 1
    assert not out.risk_authority


@pytest.mark.parametrize("pending", (1, 2, 3))
def test_pending_capital_is_not_misattributed_to_market(pending):
    row, args = case(snapshot=p8(pending=pending))
    out = audit(row, args)
    assert out.unresolved_capital_allocation
    assert "MARKET_ALLOCATION_OF_PENDING_CAPITAL_UNVERIFIED" in out.findings


def test_projection_detached_hash_tampering_fails_closed():
    row, args = case()
    with pytest.raises(ValueError, match="anchored"):
        audit_x10_reconciliation_v1(
            projection=row,
            expected_projection_sha256="f" * 64,
            **args,
        )


def test_original_p8_change_rejected_even_if_existing_projection_is_same():
    row, args = case()
    with pytest.raises(ValueError, match="digest"):
        audit(row, args, expected_p8_sha256="f" * 64)


def test_supplied_source_replay_must_match_original_projection():
    row, args = case()
    with pytest.raises(ValueError, match="reproducible"):
        audit(row, args, p8_snapshot=p8(pending=1), expected_p8_sha256=p8(pending=1).integrity_hash)


@pytest.mark.parametrize(
    "name,value",
    (
        ("capital_admission_allowed", True),
        ("risk_authority", True),
        ("certification_authority", True),
        ("independent_vote", True),
        ("deployable_capital", 1000.0),
    ),
)
def test_reconciliation_cannot_gain_risk_or_execution_authority(name, value):
    row, args = case()
    with pytest.raises(ValueError):
        replace(audit(row, args), **{name: value})
