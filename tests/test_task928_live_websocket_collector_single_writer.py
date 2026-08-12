import json

import pytest

from services.certification.task9_live_websocket_collector import (
    Task9LiveStreamCollectorLock,
    Task9LiveStreamCollectorLockError,
)


def test_first_owner_acquires_second_same_root_fails_and_release_permits_next(tmp_path):
    first = Task9LiveStreamCollectorLock(tmp_path / "stream")
    first.acquire()
    with pytest.raises(Task9LiveStreamCollectorLockError, match="TASK9_LIVE_STREAM_COLLECTOR_ALREADY_ACTIVE"):
        Task9LiveStreamCollectorLock(tmp_path / "stream").acquire()
    first.release()
    later = Task9LiveStreamCollectorLock(tmp_path / "stream"); later.acquire(); later.release()


def test_different_roots_do_not_conflict_and_lock_contains_no_credentials(tmp_path):
    left = Task9LiveStreamCollectorLock(tmp_path / "left"); right = Task9LiveStreamCollectorLock(tmp_path / "right")
    left.acquire(); right.acquire()
    raw = left.path.read_text(encoding="utf-8")
    assert set(json.loads(raw)) == {"pid", "acquired_at", "ownership_token"}
    assert "token" not in raw.lower().replace("ownership_token", "")
    left.release(); right.release()


def test_foreign_token_cannot_unlock_existing_lock(tmp_path):
    owner = Task9LiveStreamCollectorLock(tmp_path); owner.acquire()
    foreign = Task9LiveStreamCollectorLock(tmp_path); foreign._owned = True
    foreign.release()
    assert owner.path.exists()
    owner.release()
