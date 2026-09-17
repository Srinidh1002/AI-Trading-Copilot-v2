from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts import PaperOrderStateV1
from services.paper import (InMemoryPaperOrderRepository, InvalidPaperOrderTransitionError,
                            PaperOrderNotFoundError, StalePaperOrderStateError)

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def created():
    return PaperOrderStateV1("order", NOW, NOW, "CREATED", "request", "key", "NIFTY", "NSE")


def authorized(previous):
    return replace(previous, order_status="AUTHORIZED", authorization_id="auth", updated_at=NOW + timedelta(seconds=1))


def submitted(previous):
    return replace(previous, order_status="SUBMITTED", paper_candidate_id="candidate", canonical_risk_result_id="risk",
                   trading_symbol="NIFTYCE", action="BUY", option_type="CALL", position_side="LONG",
                   quantity=50, lots=1, reference_price=10.0, updated_at=NOW + timedelta(seconds=2))


def filled(previous):
    return replace(previous, order_status="FILLED", execution_result_id="result", fill_price=11.0,
                   updated_at=NOW + timedelta(seconds=3))


def test_full_legal_transition_path_and_cas():
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    second = repo.transition("order", next_state=authorized(first), expected_current_status="CREATED")
    third = repo.transition("order", next_state=submitted(second), expected_current_status="AUTHORIZED")
    final = repo.transition("order", next_state=filled(third), expected_current_status="SUBMITTED")
    assert final.order_status == "FILLED" and repo.get("order") == final and first.order_status == "CREATED"


@pytest.mark.parametrize("target", ["BLOCKED", "FAILED"])
def test_created_can_transition_to_contract_allowed_terminal_states(target):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    next_state = replace(first, order_status=target, blockers=("reason",), updated_at=NOW + timedelta(seconds=1))
    assert repo.transition("order", next_state=next_state).order_status == target


@pytest.mark.parametrize("target", ["FILLED", "CREATED", "SUBMITTED", "REJECTED", "CANCELLED"])
def test_created_rejects_illegal_transitions(target):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    if target == "FILLED": candidate = filled(submitted(authorized(first)))
    elif target in {"REJECTED", "CANCELLED"}: candidate = replace(first, order_status=target, blockers=("reason",) if target == "REJECTED" else (), warnings=("reason",) if target == "CANCELLED" else ())
    elif target == "SUBMITTED": candidate = submitted(authorized(first))
    else: candidate = replace(first, order_status=target)
    with pytest.raises(InvalidPaperOrderTransitionError): repo.transition("order", next_state=candidate)


@pytest.mark.parametrize("changes", [
    {"execution_request_id": "other"}, {"idempotency_key": "other"}, {"authorization_id": "other"},
    {"paper_candidate_id": "other"}, {"canonical_risk_result_id": "other"}, {"trading_symbol": "OTHER"},
    {"action": "SELL", "option_type": "PUT"}, {"quantity": 100}, {"lots": 2}, {"reference_price": 12.0},
])
@pytest.mark.parametrize("expected_status", [None, "SUBMITTED"])
def test_transition_rejects_changed_durable_invariants(changes, expected_status):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first); second = authorized(first); repo.transition("order", next_state=second)
    third = submitted(second); repo.transition("order", next_state=third)
    candidate = replace(filled(third), **changes)
    with pytest.raises(InvalidPaperOrderTransitionError): repo.transition("order", next_state=candidate, expected_current_status=expected_status)


@pytest.mark.parametrize("status", ["AUTHORIZED", "SUBMITTED", "FILLED", "BLOCKED", "FAILED"])
def test_stale_compare_and_set_is_rejected(status):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    candidate = replace(first, order_status="BLOCKED", blockers=("reason",), updated_at=NOW + timedelta(seconds=1))
    with pytest.raises(StalePaperOrderStateError): repo.transition("order", next_state=candidate, expected_current_status=status)


@pytest.mark.parametrize("terminal", ["FILLED", "BLOCKED", "FAILED"])
def test_terminal_state_cannot_transition(terminal):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    if terminal == "FILLED": current = repo.transition("order", next_state=authorized(first)); current = repo.transition("order", next_state=submitted(current)); current = repo.transition("order", next_state=filled(current))
    else: current = repo.transition("order", next_state=replace(first, order_status=terminal, blockers=("reason",), updated_at=NOW + timedelta(seconds=1)))
    with pytest.raises(InvalidPaperOrderTransitionError): repo.transition("order", next_state=current)


def test_missing_transition_is_not_found_and_ordering_stays_created_at():
    with pytest.raises(PaperOrderNotFoundError): InMemoryPaperOrderRepository().transition("missing", next_state=created())


def test_transition_rejects_canonical_identity_change():
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    second = authorized(first); repo.transition("order", next_state=second)
    third = submitted(second); repo.transition("order", next_state=third)
    candidate = replace(filled(third), underlying_symbol="SENSEX", exchange="BSE")
    with pytest.raises(InvalidPaperOrderTransitionError, match="underlying_symbol"):
        repo.transition("order", next_state=candidate)


@pytest.mark.parametrize("target", ["AUTHORIZED", "BLOCKED", "FAILED"])
@pytest.mark.parametrize("seconds", range(11))
def test_created_allowed_edges_preserve_atomic_timestamped_replacement(target, seconds):
    repo = InMemoryPaperOrderRepository(); first = created(); repo.save(first)
    timestamp = NOW + timedelta(seconds=seconds + 1)
    if target == "AUTHORIZED":
        candidate = replace(first, order_status=target, authorization_id="auth", updated_at=timestamp)
    else:
        candidate = replace(first, order_status=target, blockers=("reason",), updated_at=timestamp)
    stored = repo.transition("order", next_state=candidate, expected_current_status="CREATED")
    assert stored == candidate and repo.get("order") == candidate and first.order_status == "CREATED"
