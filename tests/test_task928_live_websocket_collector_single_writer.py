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

def test_dead_process_lock_is_reclaimed_without_manual_deletion(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "stream"
    root.mkdir()

    path = (
        root
        / Task9LiveStreamCollectorLock.filename
    )

    path.write_text(
        json.dumps(
            {
                "pid": 99999999,
                "acquired_at": (
                    "2026-08-18T05:01:14+00:00"
                ),
                "ownership_token": (
                    "dead-owner-token"
                ),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "services.certification."
        "task9_live_websocket_collector."
        "_task9_process_is_alive",
        lambda pid: False,
    )

    replacement = (
        Task9LiveStreamCollectorLock(
            root
        )
    )

    replacement.acquire()

    durable = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert durable["pid"] != 99999999
    assert (
        durable["ownership_token"]
        != "dead-owner-token"
    )

    replacement.release()

    assert not path.exists()


def test_live_process_lock_remains_strictly_single_writer(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "stream"
    root.mkdir()

    path = (
        root
        / Task9LiveStreamCollectorLock.filename
    )

    path.write_text(
        json.dumps(
            {
                "pid": 12345,
                "acquired_at": (
                    "2026-08-19T04:00:00+00:00"
                ),
                "ownership_token": (
                    "live-owner-token"
                ),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "services.certification."
        "task9_live_websocket_collector."
        "_task9_process_is_alive",
        lambda pid: True,
    )

    with pytest.raises(
        Task9LiveStreamCollectorLockError,
        match=(
            "TASK9_LIVE_STREAM_"
            "COLLECTOR_ALREADY_ACTIVE"
        ),
    ):
        Task9LiveStreamCollectorLock(
            root
        ).acquire()

    durable = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        durable["ownership_token"]
        == "live-owner-token"
    )


def test_malformed_existing_lock_fails_closed_and_is_not_deleted(
    tmp_path,
):
    root = tmp_path / "stream"
    root.mkdir()

    path = (
        root
        / Task9LiveStreamCollectorLock.filename
    )

    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        Task9LiveStreamCollectorLockError,
        match=(
            "TASK9_LIVE_STREAM_"
            "COLLECTOR_LOCK_CORRUPT"
        ),
    ):
        Task9LiveStreamCollectorLock(
            root
        ).acquire()

    assert path.exists()
