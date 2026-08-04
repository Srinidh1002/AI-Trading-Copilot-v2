from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from services.contracts import PaperOrderStateV1
from services.paper import DuplicatePaperOrderError, InMemoryPaperOrderRepository

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def item(n, request=None):
    return PaperOrderStateV1(f"order-{n}", NOW, NOW, "CREATED", request or f"request-{n}", f"key-{n}", "NIFTY", "NSE")


def test_simultaneous_unique_saves_are_lossless_and_coherent():
    repo = InMemoryPaperOrderRepository()
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(repo.save, [item(n) for n in range(32)]))
    assert repo.count() == 32 and len(repo.list_all()) == 32


@pytest.mark.parametrize("kind", ["order", "request"])
def test_simultaneous_duplicate_save_accepts_exactly_one(kind):
    repo = InMemoryPaperOrderRepository()
    states = [item(n, request="shared" if kind == "request" else None) for n in range(12)]
    if kind == "order": states = [item("shared", request=f"request-{n}") for n in range(12)]
    def attempt(value):
        try: repo.save(value); return True
        except DuplicatePaperOrderError: return False
    with ThreadPoolExecutor(max_workers=12) as pool: results = list(pool.map(attempt, states))
    assert results.count(True) == 1 and repo.count() == 1


@pytest.mark.parametrize("round_number", range(35))
def test_returned_collection_is_immutable_snapshot(round_number):
    repo = InMemoryPaperOrderRepository(); repo.save(item(round_number))
    snapshot = repo.list_all()
    assert isinstance(snapshot, tuple) and snapshot[0] == repo.get(f"order-{round_number}")
    with pytest.raises(AttributeError): snapshot.append(snapshot[0])


def test_clear_during_bounded_access_leaves_coherent_state():
    repo = InMemoryPaperOrderRepository()
    for n in range(20): repo.save(item(n))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda call: call(), (repo.list_all, repo.clear)))
    assert repo.count() in {0, 20}


def test_repository_construction_has_no_order_execution_side_effect():
    repo = InMemoryPaperOrderRepository()
    assert repo.count() == 0 and repo.snapshot() == ()
