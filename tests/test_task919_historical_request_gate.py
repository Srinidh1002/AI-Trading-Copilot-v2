import json

import pytest

from services.historical_request_gate import HistoricalRequestGate


class Clock:
    def __init__(self): self.now = 1000.0; self.sleeps = []
    def time(self): return self.now
    def sleep(self, seconds): self.sleeps.append(seconds); self.now += seconds


def _gate(tmp_path, clock):
    return HistoricalRequestGate(tmp_path / "gate.json", time_function=clock.time, sleep_function=clock.sleep)


def test_gate_coordinates_restart_pacing_and_sanitized_state(tmp_path):
    clock = Clock(); first = _gate(tmp_path, clock)
    assert first.acquire()["wait_seconds"] == 0.0
    second = _gate(tmp_path, clock)
    assert second.acquire()["wait_seconds"] == 1.0
    assert clock.now == 1001.0
    state = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert set(state) == {"version", "endpoint", "next_allowed_epoch_seconds"}
    assert not any(term in json.dumps(state).lower() for term in ("token", "apikey", "password", "totp", "trade", "order"))
    assert not (tmp_path / "gate.json.lock").exists()


def test_gate_recovers_stale_lock_but_never_steals_fresh_lock_or_corrupt_state(tmp_path):
    clock = Clock(); gate = _gate(tmp_path, clock); lock = tmp_path / "gate.json.lock"
    lock.write_text("1000.0", encoding="utf-8")
    assert lock.exists()
    assert clock.now - float(lock.read_text(encoding="utf-8")) < gate.stale_lock_seconds
    clock.now += 31.0
    assert gate.acquire()["wait_seconds"] == 0.0
    (tmp_path / "gate.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid historical request gate state"):
        gate.acquire()
