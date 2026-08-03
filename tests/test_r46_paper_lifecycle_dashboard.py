"""R4.6 read-only PAPER lifecycle dashboard certification."""

from dataclasses import replace
from pathlib import Path

import pytest

from dashboard.r4_paper_lifecycle_components import (
    R4_PAPER_LIFECYCLE_VIEW_STATE_KEY,
    R4PaperLifecycleDashboardViewV1,
    build_r4_paper_lifecycle_dashboard_view,
    get_r4_paper_lifecycle_dashboard_view,
    publish_r4_paper_lifecycle_dashboard_view,
    render_r4_paper_lifecycle_dashboard,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


class _FakeColumn:
    def __init__(self, calls):
        self.calls = calls

    def metric(self, label, value, *args, **kwargs):
        self.calls.append(
            ("metric", label, value, args, kwargs)
        )


class _FakeStreamlit:
    def __init__(self):
        self.calls = []

    def subheader(self, value):
        self.calls.append(("subheader", value))

    def caption(self, value):
        self.calls.append(("caption", value))

    def columns(self, count):
        self.calls.append(("columns", count))
        return tuple(
            _FakeColumn(self.calls)
            for _ in range(count)
        )

    def write(self, value):
        self.calls.append(("write", value))

    def error(self, value):
        self.calls.append(("error", value))

    def success(self, value):
        self.calls.append(("success", value))


def _open_runtime(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    entry_args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    result = execute_admitted_plan_simulated_entry(
        **entry_args
    )

    assert result.status == "OPEN"

    p7 = trade_service.get(entry_args["paper_trade_id"])
    p8 = portfolio_service.get(entry_args["portfolio_id"])

    assert p7 is not None
    assert p7.position is not None
    assert p8 is not None

    return entry_args, p7, p8


def _view(tmp_path, **changes):
    _, p7, p8 = _open_runtime(tmp_path)

    values = {
        "portfolio_snapshot": p8,
        "trade_snapshot": p7,
        "restart_status": "RECOVERED",
        "reconciliation_status": "RECONCILED",
        "reconciliation_drift_codes": (),
        "duplicate_protection_verified": True,
    }
    values.update(changes)

    return build_r4_paper_lifecycle_dashboard_view(
        **values
    )


def test_builds_exact_read_only_view_from_p7_and_p8(
    tmp_path,
):
    entry_args, p7, p8 = _open_runtime(tmp_path)

    view = build_r4_paper_lifecycle_dashboard_view(
        portfolio_snapshot=p8,
        trade_snapshot=p7,
        restart_status="RECOVERED",
        reconciliation_status="RECONCILED",
        duplicate_protection_verified=True,
    )

    position = p7.position
    assert position is not None

    reservation = p8.portfolio_snapshot.reservations[0]

    assert type(view) is R4PaperLifecycleDashboardViewV1
    assert view.portfolio_id == entry_args["portfolio_id"]
    assert view.paper_trade_id == entry_args["paper_trade_id"]
    assert view.position_id == position.position_id
    assert view.lifecycle_state == "OPEN"
    assert view.reservation_status == "ACTIVE"

    assert view.initial_quantity == position.initial_quantity
    assert (
        view.remaining_quantity
        == position.remaining_quantity
    )

    assert view.entry_price == position.entry_price
    assert (
        view.current_option_price
        == p7.latest_observation.option_last_price
    )

    assert (
        view.realized_net_pnl
        == position.realized_net_pnl
    )
    assert view.unrealized_pnl == position.unrealized_pnl
    assert view.total_pnl == position.total_pnl

    assert (
        view.remaining_capital_amount
        == reservation.remaining_capital_amount
    )
    assert (
        view.remaining_risk_amount
        == reservation.remaining_risk_amount
    )

    assert view.entry_fill_id == position.entry_fill.fill_id
    assert view.exit_fill_ids == ()
    assert view.restart_status == "RECOVERED"
    assert view.reconciliation_status == "RECONCILED"
    assert view.duplicate_protection_verified is True
    assert view.execution_mode == "PAPER"
    assert view.live_execution_eligible is False
    assert view.broker_order_submission is False


def test_publish_and_get_use_only_immutable_session_view(
    tmp_path,
):
    view = _view(tmp_path)
    session_state = {}

    publish_r4_paper_lifecycle_dashboard_view(
        session_state,
        view,
    )

    assert (
        session_state[
            R4_PAPER_LIFECYCLE_VIEW_STATE_KEY
        ]
        is view
    )

    recovered = (
        get_r4_paper_lifecycle_dashboard_view(
            session_state
        )
    )

    assert recovered is view


def test_missing_published_view_returns_none():
    assert (
        get_r4_paper_lifecycle_dashboard_view({})
        is None
    )


def test_invalid_published_type_fails_closed():
    session_state = {
        R4_PAPER_LIFECYCLE_VIEW_STATE_KEY: {
            "execution_mode": "PAPER",
        }
    }

    with pytest.raises(
        TypeError,
        match="invalid type",
    ):
        get_r4_paper_lifecycle_dashboard_view(
            session_state
        )


def test_builder_refuses_incoherent_p7_p8_projection(
    tmp_path,
):
    from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
        PaperPortfolioPersistenceSnapshotV1,
    )

    _, p7, p8 = _open_runtime(tmp_path)

    reference = (
        p8.portfolio_snapshot.position_references[0]
    )

    altered_reference = replace(
        reference,
        realized_net_pnl=reference.realized_net_pnl + 1.0,
        total_pnl=reference.total_pnl + 1.0,
    )

    altered_portfolio_snapshot = replace(
        p8.portfolio_snapshot,
        position_references=(altered_reference,),
        realized_net_pnl=(
            p8.portfolio_snapshot.realized_net_pnl + 1.0
        ),
        total_pnl=(
            p8.portfolio_snapshot.total_pnl + 1.0
        ),
        total_equity=(
            p8.portfolio_snapshot.total_equity + 1.0
        ),
        available_cash=(
            p8.portfolio_snapshot.available_cash + 1.0
        ),
        portfolio_return_fraction=(
            (
                p8.portfolio_snapshot.total_pnl + 1.0
            )
            / p8.portfolio_snapshot.starting_capital
        ),
    )

    altered_p8 = PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=p8.portfolio_id,
        portfolio_snapshot=altered_portfolio_snapshot,
        admission_idempotency_records=dict(
            p8.admission_idempotency_records
        ),
        update_idempotency_records=dict(
            p8.update_idempotency_records
        ),
        processed_portfolio_event_hashes=dict(
            p8.processed_portfolio_event_hashes
        ),
        processed_p7_transition_hashes=dict(
            p8.processed_p7_transition_hashes
        ),
        processed_p7_fill_hashes=dict(
            p8.processed_p7_fill_hashes
        ),
        created_at=p8.created_at,
        updated_at=p8.updated_at,
        event_sequence=p8.event_sequence,
    )

    with pytest.raises(
        ValueError,
        match="incoherent P7/P8 projection",
    ):
        build_r4_paper_lifecycle_dashboard_view(
            portfolio_snapshot=altered_p8,
            trade_snapshot=p7,
            restart_status="RECOVERED",
            reconciliation_status="DRIFT_DETECTED",
            reconciliation_drift_codes=(
                "POSITION_REFERENCE_REALIZED_PNL_MISMATCH",
            ),
            duplicate_protection_verified=True,
        )


def test_renderer_displays_required_lifecycle_evidence(
    tmp_path,
):
    view = _view(tmp_path)
    fake_st = _FakeStreamlit()

    render_r4_paper_lifecycle_dashboard(
        st=fake_st,
        view=view,
    )

    metrics = {
        call[1]: call[2]
        for call in fake_st.calls
        if call[0] == "metric"
    }

    assert metrics["Lifecycle"] == "OPEN"
    assert metrics["Reservation"] == "ACTIVE"
    assert metrics["Restart"] == "RECOVERED"
    assert metrics["Reconciliation"] == "RECONCILED"
    assert metrics["Contract"] == view.option_symbol
    assert metrics["Quantity"] == (
        f"{view.remaining_quantity}"
        f" / {view.initial_quantity}"
    )

    assert "Realized P&L" in metrics
    assert "Unrealized P&L" in metrics
    assert "Total P&L" in metrics
    assert "Remaining Capital" in metrics
    assert "Remaining Risk" in metrics
    assert metrics["Duplicate Protection"] == "VERIFIED"

    writes = [
        call[1]
        for call in fake_st.calls
        if call[0] == "write"
    ]

    assert len(writes) == 1
    assert writes[0]["entry_fill_id"] == view.entry_fill_id
    assert writes[0]["exit_fill_ids"] == []
    assert writes[0]["execution_mode"] == "PAPER"
    assert writes[0]["live_execution_eligible"] is False

    assert any(
        call[0] == "success"
        and "reconciled" in call[1]
        for call in fake_st.calls
    )


def test_renderer_shows_reconciliation_drift(
    tmp_path,
):
    view = replace(
        _view(tmp_path),
        reconciliation_status="DRIFT_DETECTED",
        reconciliation_drift_codes=(
            "RESERVATION_QUANTITY_MISMATCH",
        ),
    )
    fake_st = _FakeStreamlit()

    render_r4_paper_lifecycle_dashboard(
        st=fake_st,
        view=view,
    )

    assert any(
        call[0] == "error"
        and "RESERVATION_QUANTITY_MISMATCH"
        in call[1]
        for call in fake_st.calls
    )


def test_dashboard_integration_remains_read_only():
    root = Path(__file__).parents[1]

    component_source = (
        root
        / "dashboard"
        / "r4_paper_lifecycle_components.py"
    ).read_text(encoding="utf-8")

    dashboard_source = (
        root
        / "dashboard"
        / "dashboard_v2.py"
    ).read_text(encoding="utf-8")

    assert (
        "render_r4_paper_lifecycle_dashboard"
        in dashboard_source
    )
    assert (
        "_render_r4_lifecycle_section(r4_lifecycle_view)"
        in dashboard_source
    )

    forbidden_component_tokens = (
        "PaperTradePersistenceService",
        "PaperPortfolioPersistenceService",
        "execute_admitted_plan_simulated_entry",
        "execute_continuous_position_monitoring",
        "execute_position_reservation_pnl_reconciliation",
        "execute_restart_recovery",
        ".save(",
        "place_order(",
        "submit_order(",
        "broker_order_submission=True",
        "st.button(",
        "st.form(",
    )

    for token in forbidden_component_tokens:
        assert token not in component_source

    forbidden_dashboard_tokens = (
        "paper_trade_persistence_service",
        "paper_portfolio_persistence_service",
        "paper_orchestration",
        "place_order(",
        "submit_order(",
    )

    for token in forbidden_dashboard_tokens:
        assert token not in dashboard_source