"""Read-only Streamlit rendering for certified R4 PAPER lifecycle state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)


R4_PAPER_LIFECYCLE_VIEW_STATE_KEY = (
    "r4_paper_lifecycle_dashboard_view.v1"
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _number(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(
        value,
        bool,
    ):
        raise TypeError(f"{name} must be numeric")
    return float(value)


def _integer(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{name} must be an exact int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _string_tuple(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")

    result: list[str] = []

    for item in value:
        item = _text(item, name)
        if item not in result:
            result.append(item)

    return tuple(result)


@dataclass(frozen=True, slots=True)
class R4PaperLifecycleDashboardViewV1:
    portfolio_id: str
    paper_trade_id: str
    position_id: str
    underlying_symbol: str
    option_symbol: str
    lifecycle_state: str
    reservation_status: str
    initial_quantity: int
    remaining_quantity: int
    entry_price: float
    current_option_price: float | None
    realized_net_pnl: float
    unrealized_pnl: float
    total_pnl: float
    remaining_capital_amount: float
    remaining_risk_amount: float
    latest_observation_id: str | None
    latest_observation_at: datetime | None
    entry_fill_id: str
    exit_fill_ids: tuple[str, ...]
    restart_status: str
    reconciliation_status: str
    reconciliation_drift_codes: tuple[str, ...] = ()
    duplicate_protection_verified: bool = False
    updated_at: datetime | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "r4_paper_lifecycle_dashboard_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "portfolio_id",
            "paper_trade_id",
            "position_id",
            "underlying_symbol",
            "option_symbol",
            "lifecycle_state",
            "reservation_status",
            "entry_fill_id",
            "restart_status",
            "reconciliation_status",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        for name in (
            "initial_quantity",
            "remaining_quantity",
        ):
            object.__setattr__(
                self,
                name,
                _integer(getattr(self, name), name),
            )

        if self.initial_quantity <= 0:
            raise ValueError(
                "initial_quantity must be positive"
            )

        if self.remaining_quantity > self.initial_quantity:
            raise ValueError(
                "remaining_quantity cannot exceed initial"
            )

        for name in (
            "entry_price",
            "realized_net_pnl",
            "unrealized_pnl",
            "total_pnl",
            "remaining_capital_amount",
            "remaining_risk_amount",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )

        if self.current_option_price is not None:
            object.__setattr__(
                self,
                "current_option_price",
                _number(
                    self.current_option_price,
                    "current_option_price",
                ),
            )

        object.__setattr__(
            self,
            "latest_observation_id",
            _optional_text(
                self.latest_observation_id,
                "latest_observation_id",
            ),
        )

        if self.latest_observation_at is not None:
            object.__setattr__(
                self,
                "latest_observation_at",
                _aware(
                    self.latest_observation_at,
                    "latest_observation_at",
                ),
            )

        object.__setattr__(
            self,
            "exit_fill_ids",
            _string_tuple(
                self.exit_fill_ids,
                "exit_fill_ids",
            ),
        )
        object.__setattr__(
            self,
            "reconciliation_drift_codes",
            _string_tuple(
                self.reconciliation_drift_codes,
                "reconciliation_drift_codes",
            ),
        )

        if type(self.duplicate_protection_verified) is not bool:
            raise TypeError(
                "duplicate_protection_verified must be bool"
            )

        if self.updated_at is not None:
            object.__setattr__(
                self,
                "updated_at",
                _aware(self.updated_at, "updated_at"),
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError(
                "dashboard lifecycle view must remain PAPER-only"
            )

        if (
            self.schema_version
            != "r4_paper_lifecycle_dashboard_view.v1"
        ):
            raise ValueError("unsupported schema_version")


def build_r4_paper_lifecycle_dashboard_view(
    *,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
    trade_snapshot: PaperTradePersistenceSnapshotV1,
    restart_status: str,
    reconciliation_status: str,
    reconciliation_drift_codes: tuple[str, ...] = (),
    duplicate_protection_verified: bool = False,
) -> R4PaperLifecycleDashboardViewV1:
    """Project exact persisted P7/P8 state into a read-only view."""

    if (
        type(portfolio_snapshot)
        is not PaperPortfolioPersistenceSnapshotV1
    ):
        raise TypeError(
            "portfolio_snapshot must be exact "
            "PaperPortfolioPersistenceSnapshotV1"
        )

    if (
        type(trade_snapshot)
        is not PaperTradePersistenceSnapshotV1
    ):
        raise TypeError(
            "trade_snapshot must be exact "
            "PaperTradePersistenceSnapshotV1"
        )

    position = trade_snapshot.position

    if position is None:
        raise ValueError(
            "trade snapshot must contain a position"
        )

    reservations = tuple(
        item
        for item in portfolio_snapshot.portfolio_snapshot.reservations
        if item.position_id == position.position_id
    )

    if len(reservations) != 1:
        raise ValueError(
            "dashboard requires one matching reservation"
        )

    references = tuple(
        item
        for item
        in portfolio_snapshot.portfolio_snapshot.position_references
        if item.position_id == position.position_id
    )

    if len(references) != 1:
        raise ValueError(
            "dashboard requires one matching position reference"
        )

    reservation = reservations[0]
    reference = references[0]

    if (
        reference.lifecycle_state != position.lifecycle_state
        or reference.remaining_quantity
        != position.remaining_quantity
        or reference.realized_net_pnl
        != position.realized_net_pnl
        or reference.unrealized_pnl
        != position.unrealized_pnl
        or reference.total_pnl != position.total_pnl
    ):
        raise ValueError(
            "dashboard refuses incoherent P7/P8 projection"
        )

    observation = trade_snapshot.latest_observation

    return R4PaperLifecycleDashboardViewV1(
        portfolio_id=portfolio_snapshot.portfolio_id,
        paper_trade_id=trade_snapshot.paper_trade_id,
        position_id=position.position_id,
        underlying_symbol=position.underlying_symbol,
        option_symbol=position.option_symbol,
        lifecycle_state=position.lifecycle_state,
        reservation_status=reservation.reservation_status,
        initial_quantity=position.initial_quantity,
        remaining_quantity=position.remaining_quantity,
        entry_price=position.entry_price,
        current_option_price=(
            None
            if observation is None
            else observation.option_last_price
        ),
        realized_net_pnl=position.realized_net_pnl,
        unrealized_pnl=position.unrealized_pnl,
        total_pnl=position.total_pnl,
        remaining_capital_amount=(
            reservation.remaining_capital_amount
        ),
        remaining_risk_amount=(
            reservation.remaining_risk_amount
        ),
        latest_observation_id=(
            None
            if observation is None
            else observation.observation_id
        ),
        latest_observation_at=(
            None
            if observation is None
            else observation.observed_at
        ),
        entry_fill_id=position.entry_fill.fill_id,
        exit_fill_ids=tuple(
            fill.fill_id for fill in position.exit_fills
        ),
        restart_status=restart_status,
        reconciliation_status=reconciliation_status,
        reconciliation_drift_codes=(
            reconciliation_drift_codes
        ),
        duplicate_protection_verified=(
            duplicate_protection_verified
        ),
        updated_at=max(
            trade_snapshot.updated_at,
            portfolio_snapshot.updated_at,
        ),
    )


def publish_r4_paper_lifecycle_dashboard_view(
    session_state: Mapping[str, Any] | Any,
    view: R4PaperLifecycleDashboardViewV1,
) -> None:
    """Publish an immutable view into Streamlit session state."""

    if type(view) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "view must be exact "
            "R4PaperLifecycleDashboardViewV1"
        )

    session_state[R4_PAPER_LIFECYCLE_VIEW_STATE_KEY] = view


def get_r4_paper_lifecycle_dashboard_view(
    session_state: Mapping[str, Any] | Any,
) -> R4PaperLifecycleDashboardViewV1 | None:
    value = session_state.get(
        R4_PAPER_LIFECYCLE_VIEW_STATE_KEY
    )

    if value is None:
        return None

    if type(value) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "published R4 dashboard state has invalid type"
        )

    return value


def _money(value: float) -> str:
    return f"₹{value:,.2f}"


def render_r4_paper_lifecycle_dashboard(
    st: Any,
    view: R4PaperLifecycleDashboardViewV1,
) -> None:
    """Render certified state without triggering any mutation."""

    if type(view) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "view must be exact "
            "R4PaperLifecycleDashboardViewV1"
        )

    st.subheader("PAPER Portfolio Lifecycle")

    st.caption(
        "Read-only persisted P7/P8 lifecycle state. "
        "No orders or state changes can be triggered here."
    )

    state_col, reservation_col, restart_col, reconcile_col = (
        st.columns(4)
    )

    state_col.metric(
        "Lifecycle",
        view.lifecycle_state,
    )
    reservation_col.metric(
        "Reservation",
        view.reservation_status,
    )
    restart_col.metric(
        "Restart",
        view.restart_status,
    )
    reconcile_col.metric(
        "Reconciliation",
        view.reconciliation_status,
    )

    symbol_col, quantity_col, entry_col, current_col = (
        st.columns(4)
    )

    symbol_col.metric(
        "Contract",
        view.option_symbol,
    )
    quantity_col.metric(
        "Quantity",
        (
            f"{view.remaining_quantity}"
            f" / {view.initial_quantity}"
        ),
    )
    entry_col.metric(
        "Entry Price",
        f"{view.entry_price:.2f}",
    )
    current_col.metric(
        "Current Price",
        (
            "Unavailable"
            if view.current_option_price is None
            else f"{view.current_option_price:.2f}"
        ),
    )

    realized_col, unrealized_col, total_col = st.columns(3)

    realized_col.metric(
        "Realized P&L",
        _money(view.realized_net_pnl),
    )
    unrealized_col.metric(
        "Unrealized P&L",
        _money(view.unrealized_pnl),
    )
    total_col.metric(
        "Total P&L",
        _money(view.total_pnl),
    )

    capital_col, risk_col, duplicate_col = st.columns(3)

    capital_col.metric(
        "Remaining Capital",
        _money(view.remaining_capital_amount),
    )
    risk_col.metric(
        "Remaining Risk",
        _money(view.remaining_risk_amount),
    )
    duplicate_col.metric(
        "Duplicate Protection",
        (
            "VERIFIED"
            if view.duplicate_protection_verified
            else "NOT VERIFIED"
        ),
    )

    st.write(
        {
            "portfolio_id": view.portfolio_id,
            "paper_trade_id": view.paper_trade_id,
            "position_id": view.position_id,
            "underlying_symbol": view.underlying_symbol,
            "latest_observation_id": (
                view.latest_observation_id
            ),
            "latest_observation_at": (
                None
                if view.latest_observation_at is None
                else view.latest_observation_at.isoformat()
            ),
            "entry_fill_id": view.entry_fill_id,
            "exit_fill_ids": list(view.exit_fill_ids),
            "updated_at": (
                None
                if view.updated_at is None
                else view.updated_at.isoformat()
            ),
            "execution_mode": view.execution_mode,
            "live_execution_eligible": (
                view.live_execution_eligible
            ),
        }
    )

    if view.reconciliation_drift_codes:
        st.error(
            "Reconciliation drift detected: "
            + ", ".join(
                view.reconciliation_drift_codes
            )
        )
    else:
        st.success(
            "Persisted position, reservation, quantities, "
            "fills, capital, risk, and P&L are reconciled."
        )