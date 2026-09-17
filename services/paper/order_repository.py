"""Deterministic, process-local storage for immutable paper-order states.

This module deliberately knows nothing about the paper execution pipeline.  A
caller creates a :class:`PaperOrderStateV1` and explicitly stores it here.
"""
from __future__ import annotations

from dataclasses import replace
from threading import RLock

from services.contracts.paper_order_state_v1 import PaperOrderStateV1


class PaperOrderRepositoryError(ValueError):
    """Base error for deterministic paper-order repository rejections."""


class DuplicatePaperOrderError(PaperOrderRepositoryError):
    """Raised when a unique order, request, or result linkage is reused."""


class PaperOrderNotFoundError(PaperOrderRepositoryError):
    """Raised when an order is not present in this repository."""


class InvalidPaperOrderTransitionError(PaperOrderRepositoryError):
    """Raised when a replacement is not a legal order-state transition."""


class StalePaperOrderStateError(InvalidPaperOrderTransitionError):
    """Raised when a compare-and-set status does not match the stored state."""


class InMemoryPaperOrderRepository:
    """Thread-safe, deterministic storage for ``PaperOrderStateV1`` records.

    Market identity is stored explicitly by ``PaperOrderStateV1`` and is never
    derived from a trading symbol.
    """

    def __init__(self) -> None:
        self._orders: dict[str, PaperOrderStateV1] = {}
        self._request_ids: dict[str, str] = {}
        self._result_ids: dict[str, str] = {}
        self._lock = RLock()

    @staticmethod
    def _snapshot(order_state: PaperOrderStateV1) -> PaperOrderStateV1:
        if not isinstance(order_state, PaperOrderStateV1):
            raise PaperOrderRepositoryError("order_state must be PaperOrderStateV1.")
        return replace(order_state)

    @staticmethod
    def _ordered(values):
        return tuple(sorted(values, key=lambda item: (item.created_at, item.paper_order_id)))

    @staticmethod
    def _validate_transition(current: PaperOrderStateV1, next_state: PaperOrderStateV1) -> None:
        if not isinstance(next_state, PaperOrderStateV1):
            raise InvalidPaperOrderTransitionError("next_state must be PaperOrderStateV1.")
        if next_state.paper_order_id != current.paper_order_id:
            raise InvalidPaperOrderTransitionError("paper_order_id cannot change.")
        if not current.can_transition_to(next_state.order_status):
            raise InvalidPaperOrderTransitionError("Illegal paper order transition.")
        # These fields are the complete durable linkage and trading invariants
        # presently represented by PaperOrderStateV1.
        invariant_fields = (
            "execution_request_id", "idempotency_key", "authorization_id",
            "underlying_symbol", "exchange",
            "paper_candidate_id", "canonical_risk_result_id", "trading_symbol",
            "action", "option_type", "position_side", "quantity", "lots",
            "reference_price", "created_at", "schema_version", "execution_mode",
            "live_execution_eligible",
        )
        for field in invariant_fields:
            previous = getattr(current, field)
            # A later, contract-valid state may add evidence that did not exist
            # at creation; once present, that evidence is immutable.
            if previous is not None and getattr(next_state, field) != previous:
                raise InvalidPaperOrderTransitionError(f"{field} cannot change.")
        if next_state.updated_at < current.updated_at:
            raise InvalidPaperOrderTransitionError("updated_at cannot move backwards.")
        if current.execution_result_id is not None and next_state.execution_result_id != current.execution_result_id:
            raise InvalidPaperOrderTransitionError("execution_result_id cannot change.")
        if current.fill_price is not None and next_state.fill_price != current.fill_price:
            raise InvalidPaperOrderTransitionError("fill_price cannot change.")

    def save(self, order_state: PaperOrderStateV1) -> PaperOrderStateV1:
        stored = self._snapshot(order_state)
        with self._lock:
            if stored.paper_order_id in self._orders:
                raise DuplicatePaperOrderError("paper_order_id already exists.")
            if stored.execution_request_id in self._request_ids:
                raise DuplicatePaperOrderError("execution_request_id already exists.")
            if stored.execution_result_id is not None and stored.execution_result_id in self._result_ids:
                raise DuplicatePaperOrderError("execution_result_id already exists.")
            self._orders[stored.paper_order_id] = stored
            self._request_ids[stored.execution_request_id] = stored.paper_order_id
            if stored.execution_result_id is not None:
                self._result_ids[stored.execution_result_id] = stored.paper_order_id
            return self._snapshot(stored)

    add = save

    def get(self, order_id: str) -> PaperOrderStateV1 | None:
        with self._lock:
            value = self._orders.get(order_id)
            return self._snapshot(value) if value is not None else None

    def get_by_execution_request_id(self, execution_request_id: str) -> PaperOrderStateV1 | None:
        with self._lock:
            order_id = self._request_ids.get(execution_request_id)
            value = self._orders.get(order_id) if order_id is not None else None
            return self._snapshot(value) if value is not None else None

    def contains(self, order_id: str) -> bool:
        with self._lock:
            return order_id in self._orders

    def list_all(self) -> tuple[PaperOrderStateV1, ...]:
        with self._lock:
            return tuple(self._snapshot(value) for value in self._ordered(self._orders.values()))

    snapshot = list_all

    def list_by_status(self, status: str) -> tuple[PaperOrderStateV1, ...]:
        if not isinstance(status, str):
            raise PaperOrderRepositoryError("status must be a string.")
        with self._lock:
            return tuple(self._snapshot(value) for value in self._ordered(
                value for value in self._orders.values() if value.order_status == status
            ))

    def list_by_identity(self, underlying_symbol: str, exchange: str | None = None) -> tuple[PaperOrderStateV1, ...]:
        from services.core.market_identity import normalize_market_identity
        identity = normalize_market_identity(underlying_symbol, exchange)
        if identity is None:
            raise PaperOrderRepositoryError("Unsupported market identity.")
        with self._lock:
            return tuple(self._snapshot(value) for value in self._ordered(
                value for value in self._orders.values()
                if (value.underlying_symbol, value.exchange) == identity
            ))

    def transition(self, order_id: str, *, next_state: PaperOrderStateV1,
                   expected_current_status: str | None = None) -> PaperOrderStateV1:
        with self._lock:
            current = self._orders.get(order_id)
            if current is None:
                raise PaperOrderNotFoundError("paper_order_id was not found.")
            if expected_current_status is not None and current.order_status != expected_current_status:
                raise StalePaperOrderStateError("expected_current_status does not match.")
            self._validate_transition(current, next_state)
            stored = self._snapshot(next_state)
            if stored.execution_result_id is not None:
                existing = self._result_ids.get(stored.execution_result_id)
                if existing is not None and existing != order_id:
                    raise DuplicatePaperOrderError("execution_result_id already exists.")
            self._orders[order_id] = stored
            if stored.execution_result_id is not None:
                self._result_ids[stored.execution_result_id] = order_id
            return self._snapshot(stored)

    def count(self) -> int:
        with self._lock:
            return len(self._orders)

    def clear(self) -> None:
        with self._lock:
            self._orders.clear()
            self._request_ids.clear()
            self._result_ids.clear()
