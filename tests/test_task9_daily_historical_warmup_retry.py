import json

import pytest

from services.task9_daily_historical_warmup_retry import (
    BACKOFF_SECONDS,
    MAX_ATTEMPTS,
    Task9DailyWarmupRetryStore,
)


IDENTITY = "2026-08-13T00:00:00+05:30"


def _entry(**overrides):
    value = {
        "attempt_count": 1,
        "exhausted": False,
        "failure_category": "TimeoutError",
        "failed_at_epoch_seconds": 10.0,
        "next_attempt_at_epoch_seconds": 310.0,
        "required_identity": IDENTITY,
    }
    value.update(overrides)
    return value


def _document(entry):
    key = Task9DailyWarmupRetryStore.key(
        exchange="NSE", symboltoken="99926000", required_identity=IDENTITY,
    )
    return {"version": 1, "entries": {key: entry}}


@pytest.mark.parametrize("entry", (
    _entry(attempt_count=-1), _entry(attempt_count=1.5),
    _entry(attempt_count="1"), _entry(attempt_count=True),
    _entry(attempt_count=MAX_ATTEMPTS + 1),
    {key: value for key, value in _entry().items() if key != "attempt_count"},
    _entry(failed_at_epoch_seconds="bad"), _entry(next_attempt_at_epoch_seconds="bad"),
    _entry(required_identity=None), _entry(required_identity=""),
    _entry(failure_category=[]), _entry(exhausted="false"),
    _entry(exhausted=True),
    _entry(attempt_count=MAX_ATTEMPTS, exhausted=False, next_attempt_at_epoch_seconds=None),
    _entry(next_attempt_at_epoch_seconds=9.0),
))
def test_invalid_persisted_entry_is_never_accepted_or_overwritten(tmp_path, entry):
    path = tmp_path / "retry.json"
    payload = json.dumps(_document(entry), separators=(",", ":"))
    path.write_text(payload, encoding="utf-8")
    store = Task9DailyWarmupRetryStore(path, time_function=lambda: 10.0)
    for _ in range(2):
        with pytest.raises(ValueError, match="RETRY_STATE_INVALID"):
            store.status(exchange="NSE", symboltoken="99926000", required_identity=IDENTITY)
        assert path.read_text(encoding="utf-8") == payload
        store = Task9DailyWarmupRetryStore(path, time_function=lambda: 10.0)


def test_exact_four_attempt_timeline_and_identity_reset(tmp_path):
    now = [0.0]
    store = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: now[0])
    for attempt, backoff in enumerate((*BACKOFF_SECONDS, None), start=1):
        state = store.record_failure(
            exchange="NSE", symboltoken="99926000", required_identity=IDENTITY,
            failure_category="timeout",
        )
        assert state["attempt_count"] == attempt
        assert state["failed_at_epoch_seconds"] == now[0]
        assert state["exhausted"] is (attempt == MAX_ATTEMPTS)
        assert state["next_attempt_at_epoch_seconds"] == (None if backoff is None else now[0] + backoff)
        if backoff is not None:
            now[0] += backoff
    assert store.status(exchange="NSE", symboltoken="99926000", required_identity=IDENTITY)["exhausted"] is True
    next_identity = "2026-08-14T00:00:00+05:30"
    assert store.status(exchange="NSE", symboltoken="99926000", required_identity=next_identity) is None
    assert store.record_failure(exchange="NSE", symboltoken="99926000", required_identity=next_identity, failure_category="timeout")["attempt_count"] == 1


def test_two_markets_keep_four_attempt_budgets_and_keys_independent(tmp_path):
    now = [0.0]
    store = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: now[0])
    markets = (("NSE", "99926000"), ("BSE", "99919000"))
    for attempt in range(MAX_ATTEMPTS):
        for exchange, token in markets:
            state = store.record_failure(exchange=exchange, symboltoken=token, required_identity=IDENTITY, failure_category="timeout")
            assert state["attempt_count"] == attempt + 1
        if attempt < len(BACKOFF_SECONDS):
            now[0] += BACKOFF_SECONDS[attempt]
    nifty = store.status(exchange="NSE", symboltoken="99926000", required_identity=IDENTITY)
    sensex = store.status(exchange="BSE", symboltoken="99919000", required_identity=IDENTITY)
    assert nifty["exhausted"] and sensex["exhausted"]
    assert Task9DailyWarmupRetryStore.key(exchange="NSE", symboltoken="99926000", required_identity=IDENTITY) != Task9DailyWarmupRetryStore.key(exchange="BSE", symboltoken="99919000", required_identity=IDENTITY)


def test_two_market_180_cycle_persistent_failure_budget_is_exactly_eight(tmp_path):
    now = [0.0]
    store = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: now[0])
    markets = (("NSE", "99926000"), ("BSE", "99919000"))
    logical_calls = {market: 0 for market in markets}
    suppressed = 0
    for _ in range(180):
        for market in markets:
            state = store.status(exchange=market[0], symboltoken=market[1], required_identity=IDENTITY)
            eligible = state is None or (
                not state["exhausted"]
                and now[0] >= state["next_attempt_at_epoch_seconds"]
            )
            if eligible:
                logical_calls[market] += 1
                store.record_failure(exchange=market[0], symboltoken=market[1], required_identity=IDENTITY, failure_category="timeout")
            else:
                suppressed += 1
        now[0] += 60
    assert logical_calls == {markets[0]: 4, markets[1]: 4}
    assert sum(logical_calls.values()) == 8
    assert suppressed == 352
    assert all(store.status(exchange=exchange, symboltoken=token, required_identity=IDENTITY)["exhausted"] for exchange, token in markets)
