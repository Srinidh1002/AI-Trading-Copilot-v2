from datetime import datetime, timedelta, timezone

import pytest

from services.contracts import PaperOrderStateV1
from services.paper import DuplicatePaperOrderError, InMemoryPaperOrderRepository, PaperOrderRepositoryError

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def state(identifier="1", *, status="CREATED", request=None, at=NOW, **changes):
    values = dict(paper_order_id=f"order-{identifier}", created_at=at, updated_at=at,
                  order_status=status, execution_request_id=request or f"request-{identifier}",
                  idempotency_key=f"key-{identifier}", underlying_symbol="NIFTY", exchange="NSE")
    values.update(changes)
    return PaperOrderStateV1(**values)


def test_initialization_and_empty_operations():
    repo = InMemoryPaperOrderRepository()
    assert repo.count() == 0
    assert repo.list_all() == repo.snapshot() == ()
    assert repo.get("missing") is repo.get_by_execution_request_id("missing") is None
    assert not repo.contains("missing")


@pytest.mark.parametrize("identifier", range(70))
def test_save_get_and_immutable_snapshots(identifier):
    repo = InMemoryPaperOrderRepository(); original = state(str(identifier))
    assert repo.save(original) == original
    assert repo.get(original.paper_order_id) == original
    assert repo.get(original.paper_order_id) is not original
    assert repo.get_by_execution_request_id(original.execution_request_id) == original
    assert repo.contains(original.paper_order_id) and repo.count() == 1


@pytest.mark.parametrize("bad", [None, "state", 1, object()])
def test_save_rejects_wrong_types(bad):
    with pytest.raises(PaperOrderRepositoryError, match="PaperOrderStateV1"):
        InMemoryPaperOrderRepository().save(bad)


@pytest.mark.parametrize("field", ["paper_order_id", "execution_request_id"])
def test_save_rejects_duplicate_order_and_request_linkage(field):
    repo = InMemoryPaperOrderRepository(); first = state()
    repo.save(first)
    values = {field: getattr(first, field)}
    with pytest.raises(DuplicatePaperOrderError):
        repo.save(state("2", **values))
    assert repo.get(first.paper_order_id) == first and repo.count() == 1


def test_save_rejects_duplicate_execution_result_linkage():
    repo = InMemoryPaperOrderRepository()
    first = state("1", status="FILLED", authorization_id="auth", execution_result_id="result",
                  paper_candidate_id="candidate", canonical_risk_result_id="risk", trading_symbol="NIFTYCE",
                  action="BUY", option_type="CALL", position_side="LONG", quantity=50, lots=1,
                  reference_price=10.0, fill_price=11.0)
    repo.save(first)
    second = state("2", status="FILLED", authorization_id="auth2", execution_result_id="result",
                   paper_candidate_id="candidate2", canonical_risk_result_id="risk2", trading_symbol="NIFTYCE",
                   action="BUY", option_type="CALL", position_side="LONG", quantity=50, lots=1,
                   reference_price=10.0, fill_price=11.0)
    with pytest.raises(DuplicatePaperOrderError): repo.save(second)


def test_deterministic_created_at_then_order_id_ordering_and_status_filter():
    repo = InMemoryPaperOrderRepository()
    for identifier, at in (("b", NOW), ("a", NOW), ("c", NOW + timedelta(seconds=1))):
        repo.save(state(identifier, at=at))
    assert [item.paper_order_id for item in repo.list_all()] == ["order-a", "order-b", "order-c"]
    assert repo.list_by_status("BLOCKED") == ()
    assert isinstance(repo.list_all(), tuple) and isinstance(repo.list_by_status("CREATED"), tuple)


@pytest.mark.parametrize("status", ["CREATED", "AUTHORIZED", "SUBMITTED", "FILLED", "REJECTED", "BLOCKED", "CANCELLED", "FAILED"])
def test_list_by_every_contract_status(status):
    repo = InMemoryPaperOrderRepository()
    if status == "CREATED": value = state(status)
    elif status == "AUTHORIZED": value = state(status, status=status, authorization_id="auth")
    elif status == "SUBMITTED": value = state(status, status=status, authorization_id="auth", paper_candidate_id="candidate", canonical_risk_result_id="risk", trading_symbol="NIFTYCE", action="BUY", option_type="CALL", position_side="LONG", quantity=50, lots=1, reference_price=10.0)
    elif status == "FILLED": value = state(status, status=status, authorization_id="auth", execution_result_id="result", paper_candidate_id="candidate", canonical_risk_result_id="risk", trading_symbol="NIFTYCE", action="BUY", option_type="CALL", position_side="LONG", quantity=50, lots=1, reference_price=10.0, fill_price=11.0)
    elif status == "CANCELLED": value = state(status, status=status, warnings=("cancelled",))
    else: value = state(status, status=status, blockers=("blocked",))
    repo.save(value); assert repo.list_by_status(status) == (value,)


@pytest.mark.parametrize("symbol,exchange", [("NIFTY", None), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")])
def test_identity_query_validates_supported_canonical_pairs(symbol, exchange):
    repo = InMemoryPaperOrderRepository(); saved = state(symbol, underlying_symbol=symbol, exchange=exchange or ("BSE" if symbol == "SENSEX" else "NSE"))
    repo.save(saved); assert repo.list_by_identity(symbol, exchange) == (saved,)


@pytest.mark.parametrize("symbol,exchange", [("NIFTY", "BSE"), ("SENSEX", "NSE"), ("OTHER", "NSE"), ("", "NSE")])
def test_identity_query_rejects_invalid_pairs(symbol, exchange):
    with pytest.raises(PaperOrderRepositoryError, match="Unsupported market identity"):
        InMemoryPaperOrderRepository().list_by_identity(symbol, exchange)


@pytest.mark.parametrize("identifier", range(10))
def test_clear_is_explicit_and_atomic_from_caller_view(identifier):
    repo = InMemoryPaperOrderRepository(); repo.save(state(str(identifier))); repo.clear()
    assert repo.count() == 0 and repo.list_all() == ()
