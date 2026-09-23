"""Focused offline coverage for the shared cross-process lock primitive.

Gate B — Windows lock foundation repair. No real trading code is imported
or executed by any test; the only subprocesses spawned import
process_lock_v2 and nothing else.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from services.paper_orchestration.process_lock_v2 import (
    ProcessLockError,
    ProcessLockV2,
    lock_available,
)
from src import rate_limiter

_REPO = Path(__file__).resolve().parents[1]

_CHILD_HOLDER = """
import sys, time
sys.path.insert(0, sys.argv[1])
from services.paper_orchestration.process_lock_v2 import (
    ProcessLockV2, ProcessLockError,
)
path = sys.argv[2]
hold_s = float(sys.argv[3])
try:
    lock = ProcessLockV2(path, role="CHILD").acquire()
except ProcessLockError:
    print("REFUSED", flush=True)
    sys.exit(0)
print("ACQUIRED", flush=True)
time.sleep(hold_s)
lock.release()
print("RELEASED", flush=True)
"""

_CHILD_RACER = """
import sys, time, os
sys.path.insert(0, sys.argv[1])
from services.paper_orchestration.process_lock_v2 import (
    ProcessLockV2, ProcessLockError,
)
path = sys.argv[2]
out = sys.argv[3]
marker = sys.argv[4]
try:
    lock = ProcessLockV2(path, role="CHILD").acquire()
except ProcessLockError:
    with open(out, "a") as f:
        f.write("R\\n")
        f.flush()
    sys.exit(0)
with open(out, "a") as f:
    f.write("A\\n")
    f.flush()
deadline = time.time() + 10.0
while time.time() < deadline:
    if os.path.exists(marker):
        break
    time.sleep(0.005)
lock.release()
"""


def _spawn_holder(lock_path, hold_s):
    return subprocess.Popen(
        [sys.executable, "-c", _CHILD_HOLDER, str(_REPO), str(lock_path), str(hold_s)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_lock_taken(path, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if lock_available(path, role="PROBE") is False:
            return True
        time.sleep(0.05)
    return False


def _run_two_way_race(tmp_path, tag):
    lock_path = tmp_path / f"race_{tag}.lock"
    out_file = tmp_path / f"out_{tag}.txt"
    marker = tmp_path / f"go_{tag}"
    out_file.write_text("", encoding="utf-8")

    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                _CHILD_RACER,
                str(_REPO),
                str(lock_path),
                str(out_file),
                str(marker),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]

    deadline = time.time() + 15.0
    content = ""
    while time.time() < deadline:
        content = out_file.read_text(encoding="utf-8")
        if content.count("\n") >= 2:
            break
        time.sleep(0.02)
    else:
        for p in procs:
            p.kill()
        stderrs = [p.stderr.read() for p in procs]
        pytest.fail(f"{tag}: children did not report; stderr={stderrs!r}")

    marker.touch()
    for p in procs:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            pytest.fail(f"{tag}: child did not exit after marker")

    return content.strip().splitlines()


# --- 1, 2, 3, 4, 10, 12 ------------------------------------------------


def test_process_lock_acquire_release_and_metadata(tmp_path):
    path = tmp_path / "owner.lock"
    owner = ProcessLockV2(path, role="SUPERVISOR").acquire()

    metadata = json.loads(path.read_text(encoding="utf-8"))
    assert metadata["role"] == "SUPERVISOR"
    assert metadata["pid"] > 0
    assert not lock_available(path, role="PROBE")

    owner.release()
    owner.release()
    assert lock_available(path, role="PROBE") is True


def test_process_lock_blocks_double_owner_and_recovers_stale_metadata(tmp_path):
    path = tmp_path / "owner.lock"
    first = ProcessLockV2(path, role="WORKER:NIFTY").acquire()

    with pytest.raises(ProcessLockError, match="LOCK_HELD"):
        ProcessLockV2(path, role="WORKER:NIFTY").acquire()

    first.release()
    path.write_text("{malformed stale metadata", encoding="utf-8")
    recovered = ProcessLockV2(path, role="WORKER:NIFTY").acquire()
    recovered.release()


def test_lock_available_always_returns_boolean_for_normal_contention(tmp_path):
    path = tmp_path / "owner.lock"
    assert lock_available(path, role="PROBE") is True
    owner = ProcessLockV2(path, role="WORKER:SENSEX").acquire()
    assert lock_available(path, role="PROBE") is False
    owner.release()


def test_same_object_reacquire_is_idempotent(tmp_path):
    path = tmp_path / "owner.lock"
    lock = ProcessLockV2(path, role="IDEMPOTENT")
    lock.acquire()
    lock.acquire()
    assert lock.held is True
    lock.release()
    lock.release()
    assert lock.held is False


def test_metadata_readable_while_lock_held(tmp_path):
    path = tmp_path / "owner.lock"
    lock = ProcessLockV2(path, role="READABLE").acquire()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["role"] == "READABLE"
        assert data["pid"] == os.getpid()
        guard = path.with_name(path.name + ".guard")
        assert guard.exists()
        assert guard.stat().st_size <= 1
    finally:
        lock.release()


def test_lock_handle_remains_open_throughout_ownership(tmp_path):
    path = tmp_path / "owner.lock"
    lock = ProcessLockV2(path, role="HANDLE")
    lock.acquire()
    handle = lock._handle
    assert handle is not None
    assert handle.closed is False
    lock.release()
    assert handle.closed is True


# --- 5, 6, 7, 8 --------------------------------------------------------


def test_second_process_cannot_acquire_same_lock(tmp_path):
    path = tmp_path / "cross.lock"
    child = _spawn_holder(path, 1.5)
    try:
        assert _wait_for_lock_taken(path), "child never acquired the lock"
        with pytest.raises(ProcessLockError, match="LOCK_HELD"):
            ProcessLockV2(path, role="PARENT").acquire()
    finally:
        out, err = child.communicate(timeout=10)
        assert "ACQUIRED" in out, f"child stdout={out!r} stderr={err!r}"
    assert lock_available(path, role="PROBE") is True


def test_live_owner_cannot_be_stolen(tmp_path):
    path = tmp_path / "live.lock"
    child = _spawn_holder(path, 1.5)
    try:
        assert _wait_for_lock_taken(path), "child never acquired the lock"
        for _ in range(5):
            with pytest.raises(ProcessLockError, match="LOCK_HELD"):
                ProcessLockV2(path, role="ATTACK").acquire()
            time.sleep(0.05)
    finally:
        out, err = child.communicate(timeout=10)
        assert "ACQUIRED" in out, f"child stdout={out!r} stderr={err!r}"
    assert lock_available(path, role="PROBE") is True


def test_two_simultaneous_processes_exactly_one_winner(tmp_path):
    lines = _run_two_way_race(tmp_path, "single")
    winners = [ln for ln in lines if ln == "A"]
    losers = [ln for ln in lines if ln == "R"]
    assert len(winners) == 1, f"expected exactly 1 winner, got {lines!r}"
    assert len(losers) == 1, f"expected exactly 1 loser, got {lines!r}"


def test_repeat_simultaneous_acquisition_20_times(tmp_path):
    for rep in range(20):
        lines = _run_two_way_race(tmp_path, f"rep{rep}")
        winners = [ln for ln in lines if ln == "A"]
        assert len(winners) == 1, f"rep {rep}: expected exactly 1 winner, got {lines!r}"


# --- 9, 11 -------------------------------------------------------------


def test_stale_metadata_without_os_ownership_is_recovered(tmp_path):
    path = tmp_path / "stale.lock"
    path.write_text(json.dumps({"pid": 999999, "role": "DEAD"}), encoding="utf-8")
    lock = ProcessLockV2(path, role="NEW").acquire()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["role"] == "NEW"
    finally:
        lock.release()


def test_malformed_stale_metadata_does_not_create_double_ownership(tmp_path):
    path = tmp_path / "malformed.lock"
    path.write_text("{not valid json", encoding="utf-8")
    first = ProcessLockV2(path, role="A").acquire()
    try:
        with pytest.raises(ProcessLockError, match="LOCK_HELD"):
            ProcessLockV2(path, role="B").acquire()
    finally:
        first.release()


# --- 13, 14, 15 --------------------------------------------------------


def test_different_logical_locks_coexist(tmp_path):
    a = ProcessLockV2(tmp_path / "a.lock", role="A").acquire()
    b = ProcessLockV2(tmp_path / "b.lock", role="B").acquire()
    try:
        assert a.held and b.held
    finally:
        a.release()
        b.release()


def test_all_five_market_locks_coexist(tmp_path):
    markets = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
    locks = [
        ProcessLockV2(tmp_path / f"{m}.lock", role=f"WORKER:{m}").acquire()
        for m in markets
    ]
    try:
        assert all(lk.held for lk in locks)
    finally:
        for lk in locks:
            lk.release()


def test_supervisor_and_worker_locks_are_independent(tmp_path):
    sup = ProcessLockV2(tmp_path / "supervisor.lock", role="SUPERVISOR").acquire()
    worker = ProcessLockV2(
        tmp_path / "worker_NIFTY.lock", role="WORKER:NIFTY"
    ).acquire()
    try:
        assert sup.held and worker.held
    finally:
        sup.release()
        worker.release()


# --- fail-closed (kept from prior suite) -------------------------------


def test_rate_limiter_fail_closed_for_corrupt_state_and_lock_error(
    tmp_path, monkeypatch
):
    state = tmp_path / "state.json"
    state.write_text("{bad json", encoding="utf-8")
    coordinator = rate_limiter.FyersRateLimitCoordinator(state_path=state)

    with pytest.raises(rate_limiter.FyersRateLimitError, match="STATE_INVALID"):
        coordinator.wait_if_needed()

    def fail_lock(*_args, **_kwargs):
        raise rate_limiter.FileRegionLockError("offline")

    monkeypatch.setattr(rate_limiter, "acquire_file_region_lock", fail_lock)
    with pytest.raises(rate_limiter.FyersRateLimitError, match="LOCK_UNAVAILABLE"):
        rate_limiter.FyersRateLimitCoordinator(
            state_path=tmp_path / "fresh.json"
        ).wait_if_needed()


def test_shared_lock_primitive_is_platform_import_safe():
    assert callable(rate_limiter.acquire_file_region_lock)
    assert callable(rate_limiter.release_file_region_lock)
