from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from services.x1.endpoint_cache_v1 import (
    AuthEndpointNotCacheable,
    EndpointCacheError,
    EndpointCacheTimeout,
    EndpointCacheV1,
)


class WallClock:
    def __init__(self, start: datetime):
        self._t = start

    def __call__(self):
        return self._t

    def advance(self, seconds: float) -> None:
        self._t = self._t + timedelta(seconds=seconds)


class MonoClock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self):
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def make_cache(**kwargs):
    mono = MonoClock()
    wall = WallClock(datetime(2026, 9, 17, 10, 0, tzinfo=UTC))
    cache = EndpointCacheV1(
        clock=mono,
        wall_clock=wall,
        **kwargs,
    )
    return cache, mono, wall


def test_cache_miss_then_hit():
    cache, mono, _ = make_cache()
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"value": calls["n"]}

    a = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=fetch,
    )
    b = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=fetch,
    )
    assert calls["n"] == 1
    assert a.is_cached is False
    assert b.is_cached is True
    assert b.value == {"value": 1}
    assert b.cache_age_seconds == 0.0


def test_cache_expires_after_ttl():
    cache, mono, _ = make_cache()
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"value": calls["n"]}

    cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={},
        fetch=fetch, ttl_seconds=5.0,
    )
    mono.advance(6.0)
    second = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={},
        fetch=fetch, ttl_seconds=5.0,
    )
    assert calls["n"] == 2
    assert second.is_cached is False


def test_provider_isolation():
    cache, _, _ = make_cache()
    calls = {"FYERS": 0, "ANGEL": 0}

    def fetch_for(provider):
        def fetch():
            calls[provider] += 1
            return {"provider": provider}
        return fetch

    a = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=fetch_for("FYERS"),
    )
    b = cache.get_or_fetch(
        provider="ANGEL_SMARTAPI", endpoint="quotes",
        params={"s": "NIFTY"}, fetch=fetch_for("ANGEL"),
    )
    assert a.value == {"provider": "FYERS"}
    assert b.value == {"provider": "ANGEL"}
    assert calls == {"FYERS": 1, "ANGEL": 1}


def test_param_isolation():
    cache, _, _ = make_cache()
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"value": calls["n"]}

    a = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=fetch,
    )
    b = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "SENSEX"},
        fetch=fetch,
    )
    assert a.value != b.value
    assert calls["n"] == 2


def test_auth_endpoint_is_refused():
    cache, _, _ = make_cache()
    with pytest.raises(AuthEndpointNotCacheable):
        cache.get_or_fetch(
            provider="FYERS",
            endpoint="auth/token",
            params={},
            fetch=lambda: {},
        )
    with pytest.raises(AuthEndpointNotCacheable):
        cache.get_or_fetch(
            provider="FYERS",
            endpoint="session",
            params={},
            fetch=lambda: {},
        )


def test_failed_fetch_does_not_cache():
    cache, _, _ = make_cache()

    def boom():
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError):
        cache.get_or_fetch(
            provider="FYERS", endpoint="quotes", params={},
            fetch=boom,
        )
    assert cache.snapshot()["entries"] == 0


def test_non_mapping_fetch_result_is_refused():
    cache, _, _ = make_cache()
    with pytest.raises(EndpointCacheError):
        cache.get_or_fetch(
            provider="FYERS", endpoint="quotes", params={},
            fetch=lambda: "not a mapping",  # type: ignore[arg-type]
        )


def test_endpoint_specific_ttl_is_used():
    cache, mono, _ = make_cache(
        endpoint_ttl_seconds={"historical": 60.0, "quotes": 5.0},
        default_ttl_seconds=1.0,
    )
    assert cache.ttl_for("historical") == 60.0
    assert cache.ttl_for("quotes") == 5.0
    assert cache.ttl_for("unknown-endpoint") == 1.0


def test_invalidate_specific_key():
    cache, _, _ = make_cache()
    cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=lambda: {"x": 1},
    )
    assert cache.get(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"}
    ) is not None
    cache.invalidate(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"}
    )
    assert cache.get(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"}
    ) is None


def test_invalidate_provider():
    cache, _, _ = make_cache()
    cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={"s": "NIFTY"},
        fetch=lambda: {"x": 1},
    )
    cache.get_or_fetch(
        provider="ANGEL_SMARTAPI", endpoint="quotes",
        params={"s": "NIFTY"}, fetch=lambda: {"x": 2},
    )
    assert cache.invalidate_provider("FYERS") == 1
    assert cache.get(
        provider="ANGEL_SMARTAPI", endpoint="quotes",
        params={"s": "NIFTY"},
    ) is not None


def test_bounded_capacity_evicts_lru():
    cache, _, _ = make_cache(max_entries=2)
    for i in range(3):
        cache.get_or_fetch(
            provider="FYERS", endpoint="quotes", params={"n": i},
            fetch=lambda i=i: {"n": i},
        )
    assert cache.snapshot()["entries"] == 2
    # The first entry should have been evicted.
    assert cache.get(
        provider="FYERS", endpoint="quotes", params={"n": 0}
    ) is None


def test_inflight_dedup_shares_a_single_fetch():
    cache, _, _ = make_cache()
    calls = {"n": 0}
    release = threading.Event()

    def fetch():
        calls["n"] += 1
        release.wait(5.0)
        return {"value": 1}

    results = []
    errors = []

    def worker():
        try:
            r = cache.get_or_fetch(
                provider="FYERS", endpoint="quotes", params={},
                fetch=fetch, ttl_seconds=10.0,
            )
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    time.sleep(0.1)
    t2.start()
    time.sleep(0.1)
    release.set()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)
    assert calls["n"] == 1
    assert not errors
    assert len(results) == 2
    assert results[0].value == {"value": 1}
    assert results[1].value == {"value": 1}


def test_inflight_timeout_raises():
    cache, _, _ = make_cache(inflight_timeout_seconds=0.2)
    release = threading.Event()

    def slow_fetch():
        release.wait(5.0)
        return {"value": 1}

    def first_loader():
        try:
            cache.get_or_fetch(
                provider="FYERS", endpoint="quotes", params={},
                fetch=slow_fetch, ttl_seconds=10.0,
            )
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=first_loader)
    t.start()
    time.sleep(0.05)

    def second():
        cache.get_or_fetch(
            provider="FYERS", endpoint="quotes", params={},
            fetch=slow_fetch, ttl_seconds=10.0,
        )

    with pytest.raises(EndpointCacheTimeout):
        second()
    release.set()
    t.join(timeout=5.0)


def test_cache_preserves_observed_at_and_marks_cache_hits():
    cache, mono, wall = make_cache()
    first = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={},
        fetch=lambda: {"x": 1}, ttl_seconds=10.0,
    )
    mono.advance(3.0)
    wall.advance(3.0)
    second = cache.get_or_fetch(
        provider="FYERS", endpoint="quotes", params={},
        fetch=lambda: {"x": 1}, ttl_seconds=10.0,
    )
    assert second.is_cached is True
    assert second.observed_at == first.observed_at
    assert second.cache_age_seconds >= 3.0


def test_auth_prefix_matching_is_case_insensitive():
    cache, _, _ = make_cache()
    with pytest.raises(AuthEndpointNotCacheable):
        cache.get_or_fetch(
            provider="FYERS", endpoint="AUTH", params={},
            fetch=lambda: {},
        )
    with pytest.raises(AuthEndpointNotCacheable):
        cache.get_or_fetch(
            provider="FYERS", endpoint="Token/Refresh", params={},
            fetch=lambda: {},
        )
