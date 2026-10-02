"""Offline shape/guard tests using canonical-interface test doubles.

Full genuine P7/P8 persistence integration requires the complete repository
fixture in the user's worktree; these fakes do NOT certify runtime integration.
"""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace as Record

import pytest
from test_x10_readiness_v1 import NOW, ledger

from services.x7.contracts_v1 import MARKETS
from services.x10 import typed_projection_v1 as module
from services.x10.typed_projection_v1 import project_x10_typed_portfolio_v1


class FakeP8:
    """Explicit test double; never production type-check authority."""

    @property
    def integrity_hash(self):
        return sha256(
            repr(
                (
                    self.portfolio_id,
                    self.event_sequence,
                    self.portfolio_snapshot.open_position_count,
                    self.portfolio_snapshot.pending_plan_count,
                    [
                        (x.position_id, x.underlying_symbol, x.remaining_quantity)
                        for x in self.portfolio_snapshot.position_references
                    ],
                )
            ).encode()
        ).hexdigest()


class FakeP7:
    @property
    def integrity_hash(self):
        return sha256(
            repr(
                (
                    self.paper_trade_id,
                    self.event_sequence,
                    self.position.position_id,
                    self.position.remaining_quantity,
                )
            ).encode()
        ).hexdigest()


@pytest.fixture(autouse=True)
def stub_exact_canonical_classes(monkeypatch):
    monkeypatch.setattr(module, "_p8_cls", lambda: FakeP8)
    monkeypatch.setattr(module, "_p7_cls", lambda: FakeP7)


def position(market="NIFTY", pid="P1", state="OPEN", qty=50):
    return Record(
        position_id=pid,
        underlying_symbol=market,
        remaining_quantity=qty,
        lifecycle_state=state,
        transition_sequence=2,
        is_terminal=state != "OPEN",
        updated_at=NOW - timedelta(seconds=3),
    )


def p8(*, positions=(), pending=0, **kw):
    result = FakeP8()
    result.portfolio_id = "PORTFOLIO"
    result.created_at = NOW - timedelta(seconds=15)
    result.updated_at = kw.get("updated", NOW - timedelta(seconds=5))
    result.event_sequence = 3
    result.execution_mode = "PAPER"
    result.live_execution_eligible = False
    reservations = tuple(Record(reservation_status="PENDING_HOLD") for _ in range(pending))
    result.portfolio_snapshot = Record(
        portfolio_id="PORTFOLIO",
        created_at=NOW - timedelta(seconds=15),
        updated_at=kw.get("snap_updated", NOW - timedelta(seconds=5)),
        event_sequence=3,
        open_position_count=sum(not x.is_terminal for x in positions),
        pending_plan_count=pending,
        position_references=tuple(positions),
        reservations=reservations,
    )
    return result


def p7(p):
    out = FakeP7()
    out.paper_trade_id = "TRADE_" + p.position_id
    out.position = Record(
        position_id=p.position_id,
        market=p.underlying_symbol,
        remaining_quantity=p.remaining_quantity,
        lifecycle_state=p.lifecycle_state,
    )
    out.event_sequence = 3
    out.created_at = NOW - timedelta(seconds=10)
    out.updated_at = NOW - timedelta(seconds=4)
    out.execution_mode = "PAPER"
    out.live_execution_eligible = False
    return out


def view(snapshot=None, records=(), *, force_missing=False, **kw):
    parent = ledger()
    if force_missing:
        return project_x10_typed_portfolio_v1(
            ledger=parent,
            p8_snapshot=None,
            expected_p8_sha256=None,
            p8_available_at=None,
        )
    snapshot = snapshot if snapshot is not None else p8()
    expected = tuple((row.paper_trade_id, row.integrity_hash) for row in records)
    params = dict(
        ledger=parent,
        p8_snapshot=snapshot,
        expected_p8_sha256=snapshot.integrity_hash,
        p8_available_at=NOW - timedelta(seconds=2),
        p7_snapshots=records,
        expected_p7_hashes=expected,
    )
    params.update(kw)
    return project_x10_typed_portfolio_v1(**params)


def test_missing_source_is_not_zero_exposure():
    result = view(force_missing=True)
    assert result.status == "UNAVAILABLE"
    assert result.index_open_position_count is None
    assert all(row.open_position_count is None for row in result.slots)
    assert result.deployable_capital is None


def test_empty_p8_reports_index_zeros_not_mcx_zeros():
    result = view()
    assert result.status == "PARTIAL_DESCRIPTIVE"
    assert [x.open_position_count for x in result.slots] == [0, 0, None, None, None]
    assert result.shared_pending_reservation_count == 0
    assert result.position_reconciliation == "P8_ONLY_UNRECONCILED"
    assert not result.capital_admission_allowed


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_index_position_projection_and_exact_p7_match(market):
    position_ref = position(market)
    result = view(p8(positions=(position_ref,)), (p7(position_ref),))
    assert result.position_reconciliation == "P7_P8_MATCHED"
    assert result.index_open_position_count == 1
    assert result.slots[MARKETS.index(market)].open_position_count == 1
    assert all(row.source_status == "MCX_UNVERIFIED" for row in result.slots[2:])


@pytest.mark.parametrize("pending", (1, 2, 5))
def test_pending_reservations_not_falsely_allocated_to_index(pending):
    result = view(p8(pending=pending))
    assert result.shared_pending_reservation_count == pending
    assert result.slots[0].pending_reservation_count is None
    assert result.slots[1].pending_reservation_count is None
    assert result.index_open_position_count == 0


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI", "BANKNIFTY"))
def test_p8_out_of_scope_market_never_silently_dropped(market):
    with pytest.raises(ValueError, match="Out-of-scope"):
        view(p8(positions=(position(market),)))


def test_bad_p8_anchor_rejected():
    with pytest.raises(ValueError, match="digest"):
        view(expected_p8_sha256="f" * 64)


@pytest.mark.parametrize("delay", (1, 5, 50))
def test_future_p8_availability_rejected(delay):
    with pytest.raises(ValueError, match="not available"):
        view(p8_available_at=NOW + timedelta(seconds=delay))


def test_future_p8_snapshot_updated_at_rejected():
    with pytest.raises(ValueError, match="not available"):
        view(p8(snap_updated=NOW + timedelta(seconds=2)))


def test_future_p8_position_updated_at_rejected():
    item = position()
    item.updated_at = NOW + timedelta(seconds=1)
    with pytest.raises(ValueError, match="Future P8 position"):
        view(p8(positions=(item,)))


def test_p8_count_inconsistency_rejected():
    snap = p8()
    snap.portfolio_snapshot.open_position_count = 9
    with pytest.raises(ValueError, match="contradicts"):
        view(snap)


def test_p8_pending_inconsistency_rejected():
    snap = p8()
    snap.portfolio_snapshot.pending_plan_count = 4
    with pytest.raises(ValueError, match="contradicts"):
        view(snap)


def test_duplicate_p8_position_rejected():
    p = position()
    with pytest.raises(ValueError, match="Duplicate"):
        view(p8(positions=(p, p)))


def test_wrong_p7_anchor_rejected():
    p = position()
    with pytest.raises(ValueError, match="digest"):
        view(p8(positions=(p,)), (p7(p),), expected_p7_hashes=(("TRADE_P1", "f" * 64),))


def test_p7_position_missing_from_p8_rejected():
    p = position()
    with pytest.raises(ValueError, match="absent"):
        view(p8(), (p7(p),))


@pytest.mark.parametrize(
    "field,value",
    (("remaining_quantity", 1), ("lifecycle_state", "CLOSED_STOP"), ("market", "SENSEX")),
)
def test_p7_p8_position_mismatch_rejected(field, value):
    p = position()
    row = p7(p)
    setattr(row.position, field, value)
    with pytest.raises(ValueError, match="mismatch"):
        view(p8(positions=(p,)), (row,))


def test_p7_sequence_behind_p8_rejected():
    p = position()
    row = p7(p)
    row.event_sequence = 0
    with pytest.raises(ValueError, match="mismatch"):
        view(p8(positions=(p,)), (row,))


def test_wrong_p8_python_class_rejected():
    with pytest.raises(TypeError, match="canonical P8"):
        project_x10_typed_portfolio_v1(
            ledger=ledger(),
            p8_snapshot=Record(),
            expected_p8_sha256="f" * 64,
            p8_available_at=NOW,
        )


def test_missing_source_cannot_have_claimed_hash():
    with pytest.raises(ValueError, match="Unavailable"):
        project_x10_typed_portfolio_v1(
            ledger=ledger(),
            p8_snapshot=None,
            expected_p8_sha256="f" * 64,
            p8_available_at=None,
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("deployable_capital", 1000),
        ("capital_admission_allowed", True),
        ("position_authority", True),
        ("risk_authority", True),
        ("execution_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("independent_vote", True),
        ("index_open_position_count", 1),
    ),
)
def test_x10_cannot_forge_money_authority_or_counts(field, value):
    with pytest.raises(ValueError):
        replace(view(), **{field: value})


def test_p8_source_hash_and_p7_list_are_deterministic():
    p, q = position(pid="P1"), position(market="SENSEX", pid="P2")
    source = p8(positions=(p, q))
    a, b = p7(p), p7(q)
    assert view(source, (a, b)).sha256() == view(source, (b, a)).sha256()


def test_no_network_order_or_reservation_imports():
    import ast
    from pathlib import Path

    src = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(x.startswith("services.paper_portfolio") for x in names)
    assert not any(x.startswith("services.paper_trading") for x in names)
