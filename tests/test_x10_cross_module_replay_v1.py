"""B4 X9/X10 read-only linkage with explicitly substituted isolated P7/P8 doubles."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x9_provenance_replay_v1 import original
from test_x10_readiness_v1 import NOW
from test_x10_typed_projection_v1 import FakeP7, FakeP8, p7, p8, position

from services.x9.provenance_replay_v1 import replay_x9_provenance_v1
from services.x10 import typed_projection_v1 as source_module
from services.x10.cross_module_replay_v1 import replay_x10_cross_module_v1
from services.x10.reconciliation_audit_v1 import audit_x10_reconciliation_v1
from services.x10.typed_projection_v1 import project_x10_typed_portfolio_v1


@pytest.fixture(autouse=True)
def exact_doubles(monkeypatch):
    monkeypatch.setattr(source_module, "_p8_cls", lambda: FakeP8)
    monkeypatch.setattr(source_module, "_p7_cls", lambda: FakeP7)


def case(*, with_p8=True, with_position=False):
    args9 = original()
    r9 = replay_x9_provenance_v1(**args9)
    led = args9["ledger"]
    record = position("NIFTY") if with_position else None
    snap = p8(positions=(record,)) if with_position else p8() if with_p8 else None
    records = (p7(record),) if with_position else ()
    args10 = dict(
        ledger=led,
        p8_snapshot=snap,
        expected_p8_sha256=snap.integrity_hash if snap is not None else None,
        p8_available_at=NOW - timedelta(seconds=2) if snap is not None else None,
        p7_snapshots=records,
        expected_p7_hashes=tuple((r.paper_trade_id, r.integrity_hash) for r in records),
    )
    projected = project_x10_typed_portfolio_v1(**args10)
    reconciled = audit_x10_reconciliation_v1(
        projection=projected,
        expected_projection_sha256=projected.sha256(),
        **args10,
    )
    params = dict(
        ledger=led,
        x9_replay=r9,
        expected_x9_replay_sha256=r9.sha256(),
        projection=projected,
        expected_projection_sha256=projected.sha256(),
        reconciliation=reconciled,
        expected_reconciliation_sha256=reconciled.sha256(),
        **{k: v for k, v in args10.items() if k != "ledger"},
    )
    return params


@pytest.mark.parametrize("with_p8,with_position", ((False, False), (True, False), (True, True)))
def test_status_and_strictly_read_only(with_p8, with_position):
    row = replay_x10_cross_module_v1(**case(with_p8=with_p8, with_position=with_position))
    assert row.status == ("INDEX_REPLAY_RECONCILED" if with_position else "PARTIAL_RESEARCH_ONLY")
    assert not row.capital_admission_allowed and row.deployable_capital is None
    assert all(x[1] == "MCX_UNVERIFIED" for x in row.market_statuses[2:])


@pytest.mark.parametrize(
    "name",
    ("expected_x9_replay_sha256", "expected_projection_sha256", "expected_reconciliation_sha256"),
)
def test_tampered_independent_hash_fails_closed(name):
    args = case()
    args[name] = "f" * 64
    with pytest.raises(ValueError, match="digest"):
        replay_x10_cross_module_v1(**args)


def test_changed_upstream_p8_requires_reprojection():
    args = case()
    args["p8_snapshot"] = p8(pending=2)
    args["expected_p8_sha256"] = args["p8_snapshot"].integrity_hash
    with pytest.raises(ValueError, match="reproducible"):
        replay_x10_cross_module_v1(**args)


def test_no_risk_or_execution_authority():
    for name, value in (
        ("capital_admission_allowed", True),
        ("execution_authority", True),
        ("risk_authority", True),
        ("deployable_capital", 1000),
    ):
        with pytest.raises(ValueError):
            replace(replay_x10_cross_module_v1(**case()), **{name: value})
