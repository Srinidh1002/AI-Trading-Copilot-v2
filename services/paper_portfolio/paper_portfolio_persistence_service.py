"""Typed P8 persistence using the existing atomic JSON repository pattern."""
from __future__ import annotations

from datetime import datetime

from services.paper_portfolio_repository import PaperPortfolioRepository
from services.contracts.paper_capital_reservation_v1 import PaperCapitalReservationV1
from services.contracts.paper_portfolio_exposure_v1 import PaperPortfolioExposureV1
from services.contracts.paper_portfolio_lock_state_v1 import PaperPortfolioLockStateV1
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_position_reference_v1 import (
    PaperPortfolioPositionReferenceV1,
)
from services.contracts.paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1


def _dt(value):
    return datetime.fromisoformat(value) if type(value) is str else value


def _restore_reservation(data):
    value = dict(data)
    for name in ("created_at", "updated_at", "activated_at", "released_at"):
        if value.get(name) is not None:
            value[name] = _dt(value[name])
    for name in ("processed_fill_ids", "blockers", "decision_reasons", "warnings"):
        value[name] = tuple(value.get(name, ()))
    return PaperCapitalReservationV1(**value)


def _restore_position_reference(data):
    value = dict(data)
    value["updated_at"] = _dt(value["updated_at"])
    value["exit_fill_ids"] = tuple(value.get("exit_fill_ids", ()))
    return PaperPortfolioPositionReferenceV1(**value)


def _restore_exposure(data):
    return PaperPortfolioExposureV1(
        instrument_risk=data["instrument_risk"],
        direction_risk=data["direction_risk"],
        expiry_risk=data["expiry_risk"],
        correlated_index_direction_risk=data["correlated_index_direction_risk"],
        total_instrument_risk=data["total_instrument_risk"],
        total_direction_risk=data["total_direction_risk"],
        total_expiry_risk=data["total_expiry_risk"],
        total_correlated_index_direction_risk=data[
            "total_correlated_index_direction_risk"
        ],
        metric=data.get("metric", "REMAINING_RISK"),
        warnings=tuple(data.get("warnings", ())),
        execution_mode=data.get("execution_mode", "PAPER"),
        live_execution_eligible=data.get("live_execution_eligible", False),
        schema_version=data.get("schema_version", "1.0"),
    )


def _restore_lock_state(data):
    value = dict(data)
    for name in ("evaluated_at", "loss_locked_at", "profit_locked_at"):
        if value.get(name) is not None:
            value[name] = _dt(value[name])
    value["lock_reason_codes"] = tuple(value.get("lock_reason_codes", ()))
    return PaperPortfolioLockStateV1(**value)


def _restore_snapshot(data):
    if type(data) is not dict:
        raise TypeError("portfolio snapshot must be a dictionary")
    value = dict(data)
    value["reservations"] = tuple(
        _restore_reservation(item) for item in value["reservations"]
    )
    value["position_references"] = tuple(
        _restore_position_reference(item) for item in value["position_references"]
    )
    value["exposure"] = _restore_exposure(value["exposure"])
    value["lock_state"] = _restore_lock_state(value["lock_state"])
    value["created_at"] = _dt(value["created_at"])
    value["updated_at"] = _dt(value["updated_at"])
    for name in ("blockers", "decision_reasons", "warnings"):
        value[name] = tuple(value.get(name, ()))
    return PaperPortfolioSnapshotV1(**value)


def restore_paper_portfolio_persistence_snapshot(data):
    if type(data) is not dict:
        raise TypeError("persistence snapshot must be a dictionary")
    required = {
        "portfolio_id",
        "portfolio_snapshot",
        "admission_idempotency_records",
        "update_idempotency_records",
        "processed_portfolio_event_hashes",
        "processed_p7_transition_hashes",
        "processed_p7_fill_hashes",
        "created_at",
        "updated_at",
        "event_sequence",
        "execution_mode",
        "live_execution_eligible",
        "schema_version",
    }
    if not required.issubset(data):
        raise ValueError("persistence snapshot keys are incomplete")
    return PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=data["portfolio_id"],
        portfolio_snapshot=_restore_snapshot(data["portfolio_snapshot"]),
        admission_idempotency_records=data["admission_idempotency_records"],
        update_idempotency_records=data["update_idempotency_records"],
        processed_portfolio_event_hashes=data[
            "processed_portfolio_event_hashes"
        ],
        processed_p7_transition_hashes=data[
            "processed_p7_transition_hashes"
        ],
        processed_p7_fill_hashes=data["processed_p7_fill_hashes"],
        created_at=_dt(data["created_at"]),
        updated_at=_dt(data["updated_at"]),
        event_sequence=data["event_sequence"],
        execution_mode=data["execution_mode"],
        live_execution_eligible=data["live_execution_eligible"],
        schema_version=data["schema_version"],
    )


class PaperPortfolioPersistenceService:
    def __init__(self, repository):
        if not isinstance(repository, PaperPortfolioRepository):
            raise TypeError("repository must be PaperPortfolioRepository")
        self.repository = repository

    def save(self, snapshot):
        if type(snapshot) is not PaperPortfolioPersistenceSnapshotV1:
            raise TypeError("snapshot")
        state = {
            "portfolio_id": snapshot.portfolio_id,
            "trading_day_id": snapshot.portfolio_snapshot.trading_day_id,
            "status": (
                "BLOCKED"
                if snapshot.portfolio_snapshot.blockers
                else "ACTIVE"
            ),
            "typed_p8_snapshot": snapshot.to_dict(),
            "typed_p8_integrity_hash": snapshot.integrity_hash,
        }
        self.repository.save_portfolio(state)
        return snapshot

    def get(self, portfolio_id):
        state = self.repository.get_portfolio(portfolio_id)
        if state is None:
            return None
        raw = state.get("typed_p8_snapshot")
        if type(raw) is not dict:
            raise ValueError("typed_p8_snapshot missing")
        snapshot = restore_paper_portfolio_persistence_snapshot(raw)
        if state.get("typed_p8_integrity_hash") != snapshot.integrity_hash:
            raise ValueError("typed P8 snapshot integrity mismatch")
        return snapshot

    def list_all(self):
        values = []
        for state in self.repository.get_all_portfolios():
            if "typed_p8_snapshot" in state:
                values.append(self.get(state["portfolio_id"]))
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item.created_at,
                    item.portfolio_id,
                ),
            )
        )

    def list_active(self):
        return tuple(
            item
            for item in self.list_all()
            if not item.portfolio_snapshot.blockers
        )

    def get_by_trading_day(self, portfolio_id, trading_day_id):
        snapshot = self.get(portfolio_id)
        if snapshot is None:
            return None
        if snapshot.portfolio_snapshot.trading_day_id != trading_day_id:
            return None
        return snapshot

    def get_by_admission_idempotency_key(self, portfolio_id, key):
        snapshot = self.get(portfolio_id)
        if snapshot is None:
            return None
        records = dict(snapshot.admission_idempotency_records)
        return records.get(key)

    def get_by_update_idempotency_key(self, portfolio_id, key):
        snapshot = self.get(portfolio_id)
        if snapshot is None:
            return None
        records = dict(snapshot.update_idempotency_records)
        return records.get(key)
