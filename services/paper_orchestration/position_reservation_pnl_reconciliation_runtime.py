"""R4.4 explicit P7/P8 position, reservation, and P&L reconciliation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime

from services.contracts.paper_capital_reservation_v1 import (
    PaperCapitalReservationV1,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_portfolio_position_reference_v1 import (
    PaperPortfolioPositionReferenceV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_portfolio.paper_capital_reservation_manager import (
    release_paper_capital_reservation,
)
from services.paper_portfolio.paper_portfolio_aggregation import (
    aggregate_paper_portfolio,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    project_paper_portfolio_position,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio.paper_portfolio_reconciliation import (
    validate_paper_portfolio_reconciliation,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)


_STATUS_VALUES = frozenset(
    {
        "RECONCILED",
        "DRIFT_DETECTED",
        "REPAIRED",
    }
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def _replace_reservation(
    values: tuple[PaperCapitalReservationV1, ...],
    replacement: PaperCapitalReservationV1,
) -> tuple[PaperCapitalReservationV1, ...]:
    found = False
    result: list[PaperCapitalReservationV1] = []

    for item in values:
        if item.reservation_id == replacement.reservation_id:
            result.append(replacement)
            found = True
        else:
            result.append(item)

    if not found:
        raise ValueError("reconciliation reservation not found")

    return tuple(result)


def _replace_reference(
    values: tuple[PaperPortfolioPositionReferenceV1, ...],
    replacement: PaperPortfolioPositionReferenceV1,
) -> tuple[PaperPortfolioPositionReferenceV1, ...]:
    found = False
    result: list[PaperPortfolioPositionReferenceV1] = []

    for item in values:
        if item.position_id == replacement.position_id:
            result.append(replacement)
            found = True
        else:
            result.append(item)

    if not found:
        raise ValueError(
            "reconciliation position reference not found"
        )

    return tuple(result)


def _repair_payload_hash(
    *,
    portfolio_id: str,
    paper_trade_id: str,
    repair_idempotency_key: str,
    p7_snapshot: PaperTradePersistenceSnapshotV1,
) -> str:
    payload = {
        "operation": "R4.4_REPAIR_P7_P8_PROJECTION",
        "portfolio_id": portfolio_id,
        "paper_trade_id": paper_trade_id,
        "repair_idempotency_key": repair_idempotency_key,
        "p7_integrity_hash": p7_snapshot.integrity_hash,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PositionReservationPnlReconciliationResultV1:
    status: str
    drift_codes: tuple[str, ...]
    p7_snapshot: PaperTradePersistenceSnapshotV1
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1
    repair_requested: bool
    state_changed: bool
    idempotent_replay: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.status not in _STATUS_VALUES:
            raise ValueError(
                "unsupported R4.4 reconciliation status"
            )

        if type(self.drift_codes) is not tuple:
            raise TypeError(
                "drift_codes must be an exact tuple"
            )

        if any(
            type(code) is not str or not code.strip()
            for code in self.drift_codes
        ):
            raise ValueError(
                "drift_codes must contain nonblank strings"
            )

        if (
            type(self.p7_snapshot)
            is not PaperTradePersistenceSnapshotV1
        ):
            raise TypeError(
                "p7_snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )

        if (
            type(self.p8_snapshot)
            is not PaperPortfolioPersistenceSnapshotV1
        ):
            raise TypeError(
                "p8_snapshot must be exact "
                "PaperPortfolioPersistenceSnapshotV1"
            )

        for name in (
            "repair_requested",
            "state_changed",
            "idempotent_replay",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")

        if self.status == "RECONCILED":
            if self.drift_codes:
                raise ValueError(
                    "RECONCILED cannot contain drift codes"
                )

            if self.state_changed:
                raise ValueError(
                    "RECONCILED cannot change persisted state"
                )

        if self.status == "DRIFT_DETECTED":
            if not self.drift_codes:
                raise ValueError(
                    "DRIFT_DETECTED requires drift codes"
                )

            if self.repair_requested or self.state_changed:
                raise ValueError(
                    "detection-only result cannot repair state"
                )

        if self.status == "REPAIRED":
            if not self.repair_requested:
                raise ValueError(
                    "REPAIRED requires explicit repair request"
                )

            if self.drift_codes:
                raise ValueError(
                    "REPAIRED result must pass "
                    "post-repair validation"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("R4.4 must remain PAPER-only")


def _find_reservation(
    *,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
    position_id: str,
) -> PaperCapitalReservationV1:
    matches = tuple(
        reservation
        for reservation
        in portfolio_snapshot.portfolio_snapshot.reservations
        if reservation.position_id == position_id
    )

    if len(matches) != 1:
        raise ValueError(
            "exactly one reservation must match P7 position"
        )

    return matches[0]


def _find_reference(
    *,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
    position_id: str,
) -> PaperPortfolioPositionReferenceV1:
    matches = tuple(
        reference
        for reference
        in portfolio_snapshot.portfolio_snapshot.position_references
        if reference.position_id == position_id
    )

    if len(matches) != 1:
        raise ValueError(
            "exactly one position reference must match "
            "P7 position"
        )

    return matches[0]


def _detailed_drift_codes(
    *,
    p7_snapshot: PaperTradePersistenceSnapshotV1,
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1,
) -> tuple[str, ...]:
    position = p7_snapshot.position

    if position is None:
        return ("P7_POSITION_MISSING",)

    codes = list(
        validate_paper_portfolio_reconciliation(
            portfolio_snapshot=p8_snapshot.portfolio_snapshot,
            paper_trade_snapshots=(p7_snapshot,),
        )
    )

    try:
        reservation = _find_reservation(
            portfolio_snapshot=p8_snapshot,
            position_id=position.position_id,
        )
    except ValueError:
        codes.append("RESERVATION_CARDINALITY_MISMATCH")
        reservation = None

    try:
        reference = _find_reference(
            portfolio_snapshot=p8_snapshot,
            position_id=position.position_id,
        )
    except ValueError:
        codes.append(
            "POSITION_REFERENCE_CARDINALITY_MISMATCH"
        )
        reference = None

    if reservation is not None:
        if (
            reservation.trade_plan_id
            != position.trade_plan_id
            or reservation.integrated_trade_plan_result_id
            != position.integrated_trade_plan_result_id
        ):
            codes.append("RESERVATION_IDENTITY_MISMATCH")

        if (
            reservation.remaining_quantity
            != position.remaining_quantity
        ):
            codes.append("RESERVATION_QUANTITY_MISMATCH")

        if (
            reservation.last_p7_lifecycle_state
            != position.lifecycle_state
        ):
            codes.append("RESERVATION_LIFECYCLE_MISMATCH")

        if (
            reservation.last_p7_transition_sequence
            != p7_snapshot.event_sequence
        ):
            codes.append("RESERVATION_TRANSITION_MISMATCH")

        expected_fill_ids = tuple(
            sorted(
                fill.fill_id
                for fill in position.exit_fills
            )
        )

        if (
            reservation.processed_fill_ids
            != expected_fill_ids
        ):
            codes.append("RESERVATION_FILL_MISMATCH")

        terminal = (
            position.lifecycle_state.startswith("CLOSED_")
            or position.lifecycle_state
            in {"CANCELLED", "BLOCKED"}
        )

        expected_status = (
            "RELEASED" if terminal else "ACTIVE"
        )

        if reservation.reservation_status != expected_status:
            codes.append("RESERVATION_STATUS_MISMATCH")

        expected_ratio = (
            position.remaining_quantity
            / reservation.initial_quantity
        )

        expected_capital = (
            0.0
            if terminal
            else reservation.original_capital_amount
            * expected_ratio
        )

        expected_risk = (
            0.0
            if terminal
            else reservation.original_risk_amount
            * expected_ratio
        )

        if not _close(
            reservation.remaining_capital_amount,
            expected_capital,
        ):
            codes.append("RESERVATION_CAPITAL_MISMATCH")

        if not _close(
            reservation.remaining_risk_amount,
            expected_risk,
        ):
            codes.append("RESERVATION_RISK_MISMATCH")

    if reference is not None:
        identity_actual = (
            reference.trade_plan_id,
            reference.integrated_trade_plan_result_id,
            reference.selected_option_contract_id,
            reference.underlying_symbol,
            reference.exchange,
            reference.option_symbol,
        )

        identity_expected = (
            position.trade_plan_id,
            position.integrated_trade_plan_result_id,
            position.selected_option_contract_id,
            position.underlying_symbol,
            position.exchange or position.market,
            position.option_symbol,
        )

        if identity_actual != identity_expected:
            codes.append(
                "POSITION_REFERENCE_IDENTITY_MISMATCH"
            )

        if (
            reference.lifecycle_state
            != position.lifecycle_state
        ):
            codes.append(
                "POSITION_REFERENCE_LIFECYCLE_MISMATCH"
            )

        if (
            reference.transition_sequence
            != p7_snapshot.event_sequence
        ):
            codes.append(
                "POSITION_REFERENCE_TRANSITION_MISMATCH"
            )

        quantity_actual = (
            reference.initial_lot_count,
            reference.remaining_lot_count,
            reference.lot_size,
            reference.initial_quantity,
            reference.remaining_quantity,
        )

        quantity_expected = (
            position.initial_lot_count,
            position.remaining_lot_count,
            position.lot_size,
            position.initial_quantity,
            position.remaining_quantity,
        )

        if quantity_actual != quantity_expected:
            codes.append(
                "POSITION_REFERENCE_QUANTITY_MISMATCH"
            )

        expected_fill_ids = tuple(
            fill.fill_id
            for fill in position.exit_fills
        )

        if reference.exit_fill_ids != expected_fill_ids:
            codes.append(
                "POSITION_REFERENCE_FILL_MISMATCH"
            )

        if not _close(
            reference.realized_net_pnl,
            position.realized_net_pnl,
        ):
            codes.append(
                "POSITION_REFERENCE_REALIZED_PNL_MISMATCH"
            )

        if not _close(
            reference.unrealized_pnl,
            position.unrealized_pnl,
        ):
            codes.append(
                "POSITION_REFERENCE_UNREALIZED_PNL_MISMATCH"
            )

        if not _close(
            reference.total_pnl,
            position.total_pnl,
        ):
            codes.append(
                "POSITION_REFERENCE_TOTAL_PNL_MISMATCH"
            )

        expected_observation_id = (
            None
            if p7_snapshot.latest_observation is None
            else p7_snapshot.latest_observation.observation_id
        )

        if (
            reference.last_observation_id
            != expected_observation_id
        ):
            codes.append(
                "POSITION_REFERENCE_OBSERVATION_MISMATCH"
            )

        if reservation is not None:
            capital_actual = (
                reference.initial_capital_amount,
                reference.remaining_capital_amount,
                reference.initial_risk_amount,
                reference.remaining_risk_amount,
            )

            capital_expected = (
                reservation.original_capital_amount,
                reservation.remaining_capital_amount,
                reservation.original_risk_amount,
                reservation.remaining_risk_amount,
            )

            if capital_actual != capital_expected:
                codes.append(
                    "POSITION_REFERENCE_CAPITAL_RISK_MISMATCH"
                )

    if p7_snapshot.pnl_evidence is not None:
        evidence = p7_snapshot.pnl_evidence

        if evidence.position_id != position.position_id:
            codes.append(
                "PNL_EVIDENCE_POSITION_MISMATCH"
            )

        if (
            evidence.remaining_quantity
            != position.remaining_quantity
        ):
            codes.append(
                "PNL_EVIDENCE_QUANTITY_MISMATCH"
            )

        if not _close(
            evidence.realized_net_pnl_after,
            position.realized_net_pnl,
        ):
            codes.append(
                "PNL_EVIDENCE_REALIZED_MISMATCH"
            )

        if not _close(
            evidence.unrealized_pnl_after,
            position.unrealized_pnl,
        ):
            codes.append(
                "PNL_EVIDENCE_UNREALIZED_MISMATCH"
            )

        if not _close(
            evidence.total_pnl_after,
            position.total_pnl,
        ):
            codes.append(
                "PNL_EVIDENCE_TOTAL_MISMATCH"
            )

    return tuple(dict.fromkeys(codes))


def execute_position_reservation_pnl_reconciliation(
    *,
    portfolio_id: str,
    paper_trade_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    reconciled_at: datetime,
    repair_requested: bool,
    repair_idempotency_key: str,
    result_snapshot_id: str,
    portfolio_event_id: str,
    portfolio_persistence_service: PaperPortfolioPersistenceService,
    trade_persistence_service: PaperTradePersistenceService,
    broker_order_submission: bool = False,
) -> PositionReservationPnlReconciliationResultV1:
    """Detect drift and optionally repair P8 from P7."""

    if type(portfolio_policy) is not PaperPortfolioPolicyV1:
        raise TypeError(
            "portfolio_policy must be exact "
            "PaperPortfolioPolicyV1"
        )

    if (
        type(portfolio_persistence_service)
        is not PaperPortfolioPersistenceService
    ):
        raise TypeError(
            "portfolio_persistence_service must be exact "
            "PaperPortfolioPersistenceService"
        )

    if (
        type(trade_persistence_service)
        is not PaperTradePersistenceService
    ):
        raise TypeError(
            "trade_persistence_service must be exact "
            "PaperTradePersistenceService"
        )

    if type(repair_requested) is not bool:
        raise TypeError("repair_requested must be bool")

    portfolio_id = _text(
        portfolio_id,
        "portfolio_id",
    )
    paper_trade_id = _text(
        paper_trade_id,
        "paper_trade_id",
    )
    repair_idempotency_key = _text(
        repair_idempotency_key,
        "repair_idempotency_key",
    )
    result_snapshot_id = _text(
        result_snapshot_id,
        "result_snapshot_id",
    )
    portfolio_event_id = _text(
        portfolio_event_id,
        "portfolio_event_id",
    )
    reconciled_at = _aware(
        reconciled_at,
        "reconciled_at",
    )

    if broker_order_submission is not False:
        raise ValueError(
            "order submission must remain disabled"
        )

    p8_snapshot = portfolio_persistence_service.get(
        portfolio_id
    )

    if p8_snapshot is None:
        raise ValueError("persisted P8 portfolio not found")

    if p8_snapshot.portfolio_id != portfolio_id:
        raise ValueError(
            "persisted portfolio identity mismatch"
        )

    if (
        p8_snapshot.portfolio_snapshot.portfolio_policy_id
        != portfolio_policy.portfolio_policy_id
    ):
        raise ValueError(
            "persisted portfolio policy mismatch"
        )

    update_records = dict(
        p8_snapshot.update_idempotency_records
    )

    prior_update = update_records.get(
        repair_idempotency_key
    )

    p7_snapshot = trade_persistence_service.get(
        paper_trade_id
    )

    if p7_snapshot is None:
        if repair_requested and prior_update is not None:
            raise ValueError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT"
            )

        raise ValueError("persisted P7 trade not found")

    if p7_snapshot.position is None:
        raise ValueError("persisted P7 position missing")

    payload_hash = _repair_payload_hash(
        portfolio_id=portfolio_id,
        paper_trade_id=paper_trade_id,
        repair_idempotency_key=repair_idempotency_key,
        p7_snapshot=p7_snapshot,
    )

    if prior_update is not None:
        if prior_update != payload_hash:
            raise ValueError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT"
            )

        current_codes = _detailed_drift_codes(
            p7_snapshot=p7_snapshot,
            p8_snapshot=p8_snapshot,
        )

        if current_codes:
            raise ValueError(
                "reconciliation idempotency record exists "
                "but drift remains"
            )

        return PositionReservationPnlReconciliationResultV1(
            status="REPAIRED",
            drift_codes=(),
            p7_snapshot=p7_snapshot,
            p8_snapshot=p8_snapshot,
            repair_requested=True,
            state_changed=False,
            idempotent_replay=True,
        )

    drift_codes = _detailed_drift_codes(
        p7_snapshot=p7_snapshot,
        p8_snapshot=p8_snapshot,
    )

    if not drift_codes:
        return PositionReservationPnlReconciliationResultV1(
            status="RECONCILED",
            drift_codes=(),
            p7_snapshot=p7_snapshot,
            p8_snapshot=p8_snapshot,
            repair_requested=repair_requested,
            state_changed=False,
        )

    if not repair_requested:
        return PositionReservationPnlReconciliationResultV1(
            status="DRIFT_DETECTED",
            drift_codes=drift_codes,
            p7_snapshot=p7_snapshot,
            p8_snapshot=p8_snapshot,
            repair_requested=False,
            state_changed=False,
        )

    position = p7_snapshot.position

    reservation = _find_reservation(
        portfolio_snapshot=p8_snapshot,
        position_id=position.position_id,
    )

    event_records = dict(
        p8_snapshot.processed_portfolio_event_hashes
    )

    prior_event = event_records.get(
        portfolio_event_id
    )

    if (
        prior_event is not None
        and prior_event != payload_hash
    ):
        raise ValueError(
            "portfolio event payload conflict"
        )

    repaired_reservation = (
        release_paper_capital_reservation(
            reservation=reservation,
            position=position,
            updated_at=reconciled_at,
            p7_transition_sequence=(
                p7_snapshot.event_sequence
            ),
        )
    )

    repaired_reference = (
        project_paper_portfolio_position(
            portfolio_id=portfolio_id,
            reservation=repaired_reservation,
            position=position,
            transition_sequence=(
                p7_snapshot.event_sequence
            ),
            updated_at=reconciled_at,
            last_observation_id=(
                None
                if p7_snapshot.latest_observation is None
                else (
                    p7_snapshot.latest_observation
                    .observation_id
                )
            ),
        )
    )

    repaired_snapshot = aggregate_paper_portfolio(
        portfolio_snapshot_id=result_snapshot_id,
        portfolio_id=portfolio_id,
        policy=portfolio_policy,
        trading_day_id=(
            p8_snapshot.portfolio_snapshot.trading_day_id
        ),
        starting_capital=(
            p8_snapshot.portfolio_snapshot.starting_capital
        ),
        reservations=_replace_reservation(
            p8_snapshot.portfolio_snapshot.reservations,
            repaired_reservation,
        ),
        position_references=_replace_reference(
            p8_snapshot.portfolio_snapshot.position_references,
            repaired_reference,
        ),
        event_sequence=p8_snapshot.event_sequence + 1,
        created_at=(
            p8_snapshot.portfolio_snapshot.created_at
        ),
        updated_at=reconciled_at,
        previous_lock_state=(
            p8_snapshot.portfolio_snapshot.lock_state
        ),
        blockers=(
            p8_snapshot.portfolio_snapshot.blockers
        ),
        decision_reasons=(
            p8_snapshot.portfolio_snapshot.decision_reasons
        ),
        warnings=(
            p8_snapshot.portfolio_snapshot.warnings
        ),
    )

    update_records[repair_idempotency_key] = payload_hash
    event_records[portfolio_event_id] = payload_hash

    repaired_envelope = (
        PaperPortfolioPersistenceSnapshotV1(
            portfolio_id=portfolio_id,
            portfolio_snapshot=repaired_snapshot,
            admission_idempotency_records=dict(
                p8_snapshot.admission_idempotency_records
            ),
            update_idempotency_records=update_records,
            processed_portfolio_event_hashes=(
                event_records
            ),
            processed_p7_transition_hashes=dict(
                p8_snapshot.processed_p7_transition_hashes
            ),
            processed_p7_fill_hashes=dict(
                p8_snapshot.processed_p7_fill_hashes
            ),
            created_at=p8_snapshot.created_at,
            updated_at=reconciled_at,
            event_sequence=(
                repaired_snapshot.event_sequence
            ),
        )
    )

    persisted_repair = (
        portfolio_persistence_service.save(
            repaired_envelope
        )
    )

    post_repair_codes = _detailed_drift_codes(
        p7_snapshot=p7_snapshot,
        p8_snapshot=persisted_repair,
    )

    if post_repair_codes:
        raise ValueError(
            "reconciliation repair failed: "
            + ",".join(post_repair_codes)
        )

    return PositionReservationPnlReconciliationResultV1(
        status="REPAIRED",
        drift_codes=(),
        p7_snapshot=p7_snapshot,
        p8_snapshot=persisted_repair,
        repair_requested=True,
        state_changed=True,
    )