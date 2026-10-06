from __future__ import annotations

import json

from rate_limiter import FyersRateLimitCoordinator


class FakeClock:
    def __init__(self, start=1_000.0):
        self.now = float(start)
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(float(seconds))
        self.now += float(seconds)


def test_legacy_calls_only_state_is_backward_compatible(tmp_path, monkeypatch):
    import rate_limiter

    clock = FakeClock()
    monkeypatch.setattr(rate_limiter.time, "time", clock.time)

    state = tmp_path / "state.json"
    state.write_text(json.dumps({"calls": [999.5]}), encoding="utf-8")

    coordinator = FyersRateLimitCoordinator(state_path=state, worker_name="test")
    stats = coordinator.stats()

    assert stats["day"] == 1
    assert stats["rate_limit_streak"] == 0
    assert stats["cooldown_remaining"] == 0.0


def test_provider_rate_limit_creates_cross_process_cooldown(tmp_path, monkeypatch):
    import rate_limiter

    clock = FakeClock()
    monkeypatch.setattr(rate_limiter.time, "time", clock.time)
    monkeypatch.setattr(rate_limiter.time, "sleep", clock.sleep)

    state = tmp_path / "state.json"
    first = FyersRateLimitCoordinator(state_path=state, worker_name="one")
    second = FyersRateLimitCoordinator(state_path=state, worker_name="two")

    cooldown = first.record_rate_limit("history")
    assert cooldown == 5.0

    second.wait_if_needed("depth")

    assert clock.sleeps
    assert sum(clock.sleeps) >= 5.0

    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["rate_limit_streak"] == 1
    assert len(payload["calls"]) == 1


def test_repeated_429s_escalate_shared_cooldown(tmp_path, monkeypatch):
    import rate_limiter

    clock = FakeClock()
    monkeypatch.setattr(rate_limiter.time, "time", clock.time)

    coordinator = FyersRateLimitCoordinator(
        state_path=tmp_path / "state.json",
        worker_name="test",
    )

    assert coordinator.record_rate_limit("history") == 5.0
    clock.now += 1.0
    assert coordinator.record_rate_limit("history") == 10.0
    clock.now += 1.0
    assert coordinator.record_rate_limit("depth") == 20.0

    stats = coordinator.stats()
    assert stats["rate_limit_streak"] == 3
    assert stats["cooldown_remaining"] > 0
