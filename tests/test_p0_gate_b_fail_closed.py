"""Gate B — STEP 7 fail-closed coverage.

Every test writes only under pytest tmp_path. No live repo state is touched.
Provider calls are mocked — no FYERS, no network, no workers.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from services.paper_orchestration import process_lock_v2 as pl
from src import rate_limiter

REPO = Path(__file__).resolve().parents[1]


_HOLD_CHILD = """
import sys, time
sys.path.insert(0, sys.argv[1])
from services.paper_orchestration.process_lock_v2 import acquire_file_region_lock
lock_path, marker, hold_s = sys.argv[2], sys.argv[3], float(sys.argv[4])
handle = open(lock_path, "a+b")
acquire_file_region_lock(handle, blocking=True)
open(marker, "w").close()
time.sleep(hold_s)
"""


# ---------- state / lock fail-closed ------------------------------------


def test_corrupt_json_state_fails_closed(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{bad json", encoding="utf-8")
    coord = rate_limiter.FyersRateLimitCoordinator(state_path=state)
    with pytest.raises(rate_limiter.FyersRateLimitError, match="STATE_INVALID"):
        coord.wait_if_needed()


def test_invalid_schema_fails_closed(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"calls": "not-a-list"}), encoding="utf-8")
    coord = rate_limiter.FyersRateLimitCoordinator(state_path=state)
    with pytest.raises(rate_limiter.FyersRateLimitError, match="STATE_INVALID"):
        coord.wait_if_needed()


def test_unwritable_state_location_fails_closed(tmp_path):
    # state_path points at a directory; mkstemp inside its parent will still
    # work, but reading it as JSON will fail closed on first pass.
    state = tmp_path / "state_dir"
    state.mkdir()
    coord = rate_limiter.FyersRateLimitCoordinator(state_path=state)
    with pytest.raises(rate_limiter.FyersRateLimitError):
        coord.wait_if_needed()


def test_lock_internal_error_fails_closed(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    coord = rate_limiter.FyersRateLimitCoordinator(state_path=state)

    def fail_lock(*_a, **_k):
        raise rate_limiter.FileRegionLockError("forced")

    monkeypatch.setattr(rate_limiter, "acquire_file_region_lock", fail_lock)
    with pytest.raises(rate_limiter.FyersRateLimitError, match="LOCK_UNAVAILABLE"):
        coord.wait_if_needed()


def test_metadata_failure_after_guard_acquired_releases_guard(tmp_path, monkeypatch):
    path = tmp_path / "meta.lock"
    orig = pl._atomic_write_json

    def fake_write(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(pl, "_atomic_write_json", fake_write)
    with pytest.raises(pl.ProcessLockError, match="LOCK_METADATA_WRITE_FAILED"):
        pl.ProcessLockV2(path, role="T").acquire()

    monkeypatch.setattr(pl, "_atomic_write_json", orig)
    lock = pl.ProcessLockV2(path, role="T2").acquire()
    lock.release()


def test_another_process_holds_lock_no_bypass(tmp_path):
    state = tmp_path / "state.json"
    lock_path = state.with_suffix(state.suffix + ".lock")
    marker = tmp_path / "held.marker"

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _HOLD_CHILD,
            str(REPO),
            str(lock_path),
            str(marker),
            "1.2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 5.0
        while not marker.exists():
            if time.time() > deadline:
                pytest.fail("child never acquired the shared lock")
            time.sleep(0.02)

        coord = rate_limiter.FyersRateLimitCoordinator(state_path=state)
        t0 = time.time()
        coord.wait_if_needed("probe")
        elapsed = time.time() - t0
        # The child held the guard for 1.2 s; parent must have waited.
        assert elapsed >= 0.5, f"parent bypassed the held lock (elapsed={elapsed:.3f}s)"
        # A real permit was granted (i.e., no silent bypass)
        data = json.loads(state.read_text(encoding="utf-8"))
        assert len(data["calls"]) == 1
    finally:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()


# ---------- provider routing mocks ---------------------------------------


def test_mcx_limiter_failure_blocks_provider_mock(monkeypatch):
    """Limiter failure must prevent the provider method from running.

    Contract: no provider call may occur without a granted permit. The
    MCX wrappers may return None on limiter failure (existing behavior);
    the invariant under test is that obj.getMarketData / obj.ltpData is
    never invoked once the limiter raises.
    """
    sys.path.insert(0, str(REPO / "src"))
    from mcx import mcx_paper_bot as m

    class RaisingLimiter:
        def wait_if_needed(self, *_a, **_k):
            raise rate_limiter.FyersRateLimitError("simulated limiter failure")

    monkeypatch.setattr(m, "_get_mcx_rate_limiter", lambda: RaisingLimiter())

    class FakeObj:
        def __init__(self):
            self.calls = 0

        def getMarketData(self, *_a, **_k):
            self.calls += 1
            return {"data": {"fetched": []}}

        def ltpData(self, *_a, **_k):
            self.calls += 1
            return {"data": {}}

    # fetch_full_quote — limiter gate before provider call
    obj = FakeObj()
    result = m.fetch_full_quote(obj, "TOKEN")
    assert result is None, "fail-closed wrapper should return None on limiter failure"
    assert obj.calls == 0, (
        f"provider was reached ({obj.calls} calls) despite limiter failure"
    )

    # fetch_ltp — delegates to fetch_full_quote; must inherit the gate
    obj = FakeObj()
    ltp = m.fetch_ltp(obj, "TOKEN")
    assert ltp == 0.0, "fetch_ltp should return 0.0 when the gate fails closed"
    assert obj.calls == 0, (
        f"provider was reached ({obj.calls} calls) despite limiter failure"
    )

    # fetch_execution_quote_or_none — limiter gate before provider call
    obj = FakeObj()
    q = m.fetch_execution_quote_or_none(obj, "CRUDEOILM", "TOKEN")
    assert q is None, "execution quote should be None on limiter failure"
    assert obj.calls == 0, (
        f"provider was reached ({obj.calls} calls) despite limiter failure"
    )


def test_index_limiter_failure_blocks_provider_mock():
    """_route_rate_limited must propagate a limiter failure.

    Every provider call in target_focused_bot.py is preceded by an
    _route_rate_limited(self, ...) gate. Proving the gate re-raises on
    limiter failure proves the fail-closed invariant for the index engine.
    """
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO))
    from target_focused_bot import _route_rate_limited

    class RaisingLimiter:
        def wait_if_needed(self, *_a, **_k):
            raise rate_limiter.FyersRateLimitError("simulated limiter failure")

    class FakeBot:
        rate_limiter = RaisingLimiter()
        provider_calls = 0

        def get_provider_quote(self, *_a, **_k):
            FakeBot.provider_calls += 1
            return {"ltp": 100.0}

    bot = FakeBot()
    # The real call site pattern is:
    #     _route_rate_limited(self, "ltp_data")
    #     result = self.<provider_method>(...)
    # Here the first line must raise, so the second line never runs.
    with pytest.raises(RuntimeError, match="RATE_LIMIT_HOLD"):
        _route_rate_limited(bot, "ltp_data")
    assert bot.provider_calls == 0, "provider was reached despite limiter failure"


def test_mcx_null_limiter_does_not_exist():
    """Null limiter artifacts must not exist under src/ or services/.

    The scan is deliberately scoped to production code only — test files and
    diagnostics archives legitimately contain these strings in negative
    assertions and are excluded by design.
    """
    needles = ("NullRateLimiter", "NullLimiter", "NullRateLimitCoordinator")
    scan_roots = [REPO / "src", REPO / "services"]
    hits = []
    for root in scan_roots:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:  # noqa: S112, BLE001
                continue
            for n in needles:
                if n in text:
                    hits.append((str(p.relative_to(REPO)), n))
    assert not hits, f"Null limiter artifacts found in production code: {hits}"
