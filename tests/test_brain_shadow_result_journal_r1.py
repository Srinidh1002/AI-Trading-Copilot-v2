"""Adversarial accounting and publication tests for the B4.6 freeze."""

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from test_brain_shadow_result_journal_v1 import STAMP, _pair, _paths

import services.brain.shadow_result_journal_v1 as journal
from services.brain.shadow_result_persistence_v1 import persist_shadow_result_record_v1

SESSION = "2026-09-30"
READERS = (
    journal.enumerate_shadow_result_journal_v1,
    journal.replay_shadow_result_journal_v1,
    journal.verify_shadow_result_journal_v1,
)


def capture(root, **kwargs):
    snapshot, result = _pair(**kwargs)
    return journal.capture_shadow_result_journal_v1(
        journal_root=root, session_id=SESSION, snapshot=snapshot, result=result
    )


def read(root, reader=journal.verify_shadow_result_journal_v1):
    return reader(journal_root=root, market="NIFTY", session_id=SESSION)


def file_bytes(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("populated", (False, True))
def test_valid_orphan_record_fails_every_reader(tmp_path, reader, populated):
    if populated:
        capture(tmp_path)
    _, orphan = _pair(runtime="ORPHAN", stamp=STAMP + timedelta(minutes=1))
    path = tmp_path / "NIFTY" / SESSION / "records" / f"{orphan.shadow_result_sha256}.json"
    persist_shadow_result_record_v1(orphan, path)
    before = file_bytes(tmp_path)
    with pytest.raises(journal.ShadowResultJournalIntegrityError, match="record"):
        read(tmp_path, reader)
    assert file_bytes(tmp_path) == before


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("artifact", ("unexpected.tmp", ".hidden", "nested", "bad.json"))
def test_unexpected_record_entry_fails(tmp_path, reader, artifact):
    entry = capture(tmp_path)
    path = _paths(tmp_path, entry)["record"].parent / artifact
    if artifact == "nested":
        path.mkdir()
    else:
        path.write_text("{}", encoding="utf-8")
    with pytest.raises(journal.ShadowResultJournalReplayError):
        read(tmp_path, reader)


@pytest.mark.parametrize("reader", READERS)
def test_missing_record_fails_enumeration_too(tmp_path, reader):
    entry = capture(tmp_path)
    _paths(tmp_path, entry)["record"].unlink()
    with pytest.raises(journal.ShadowResultJournalIntegrityError):
        read(tmp_path, reader)


def test_forced_same_slot_race_leaves_exactly_one_record(tmp_path, monkeypatch):
    # Both old writers reach this barrier AFTER publishing their records.
    # Fixed writers reach it BEFORE either is allowed to publish a record.
    barrier = Barrier(2)
    original = journal._publish_immutable_text

    def publish(path, text):
        if path.parent.name == "slots":
            barrier.wait(timeout=10)
        return original(path, text)

    monkeypatch.setattr(journal, "_publish_immutable_text", publish)

    def worker(runtime):
        try:
            return capture(tmp_path, runtime=runtime)
        except journal.ShadowResultJournalConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ("RACE_A", "RACE_B")))
    winners = [entry for entry in results if entry is not None]
    assert len(winners) == 1
    records = list((tmp_path / "NIFTY" / SESSION / "records").iterdir())
    assert records == [_paths(tmp_path, winners[0])["record"]]
    assert read(tmp_path).entry_count == 1


@pytest.mark.parametrize("stage", ("slot", "record", "manifest"))
def test_interrupted_publication_exact_retry_preserves_claim(tmp_path, monkeypatch, stage):
    original_publish = journal._publish_immutable_text
    original_persist = journal.persist_shadow_result_record_v1

    def publish(path, text):
        if stage == "slot" and path.parent.name == "slots":
            original_publish(path, text)
            raise OSError("injected interruption after slot claim")
        if stage == "manifest" and path.parent.name == "manifest":
            raise OSError("injected interruption before manifest")
        return original_publish(path, text)

    def persist(result, path):
        if stage == "record":
            raise OSError("injected interruption before record")
        return original_persist(result, path)

    with monkeypatch.context() as patch:
        patch.setattr(journal, "_publish_immutable_text", publish)
        patch.setattr(journal, "persist_shadow_result_record_v1", persist)
        with pytest.raises(OSError, match="injected interruption"):
            capture(tmp_path, runtime="CLAIM_OWNER")

    before = file_bytes(tmp_path)
    with pytest.raises(journal.ShadowResultJournalIntegrityError):
        read(tmp_path)
    with pytest.raises(journal.ShadowResultJournalConflictError):
        capture(tmp_path, runtime="DIFFERENT_WRITER")
    assert file_bytes(tmp_path) == before
    entry = capture(tmp_path, runtime="CLAIM_OWNER")
    assert read(tmp_path).entry_count == 1
    assert capture(tmp_path, runtime="CLAIM_OWNER") == entry
    for path, data in before.items():
        assert (tmp_path / path).read_bytes() == data


def test_completed_manifest_survives_lost_acknowledgement(tmp_path, monkeypatch):
    original = journal._publish_immutable_text

    def publish(path, text):
        result = original(path, text)
        if path.parent.name == "manifest":
            raise OSError("injected lost acknowledgement")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(journal, "_publish_immutable_text", publish)
        with pytest.raises(OSError):
            capture(tmp_path)
    before = file_bytes(tmp_path)
    assert read(tmp_path).entry_count == 1
    capture(tmp_path)
    assert file_bytes(tmp_path) == before


@pytest.mark.parametrize("artifact", ("record", "slot", "manifest", "records_dir", "session"))
@pytest.mark.parametrize("dangling", (False, True))
def test_linked_artifacts_are_rejected(tmp_path, artifact, dangling):
    entry = capture(tmp_path)
    paths = _paths(tmp_path, entry)
    if artifact == "records_dir":
        target = paths["record"].parent
    elif artifact == "session":
        target = paths["root"]
    else:
        target = paths[artifact]
    saved = tmp_path / "outside"
    is_dir = target.is_dir()
    target.rename(saved)
    try:
        target.symlink_to(tmp_path / "absent" if dangling else saved, target_is_directory=is_dir)
    except OSError as exc:
        saved.rename(target)
        pytest.skip(f"symlink capability unavailable: {exc}")
    with pytest.raises(journal.ShadowResultJournalIntegrityError):
        read(tmp_path)


def _process_capture(root, runtime, start, queue):
    if not start.wait(timeout=20):
        queue.put("TIMEOUT")
        return
    try:
        capture(Path(root), runtime=runtime)
        queue.put("OK")
    except journal.ShadowResultJournalConflictError:
        queue.put("CONFLICT")


@pytest.mark.parametrize("identical", (False, True))
def test_spawned_process_writers_are_conflict_safe(tmp_path, identical):
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    queue = ctx.Queue()
    runtimes = ["SAME", "SAME"] if identical else ["FIRST", "SECOND"]
    processes = [
        ctx.Process(target=_process_capture, args=(str(tmp_path), runtime, start, queue))
        for runtime in runtimes
    ]
    try:
        for process in processes:
            process.start()
        start.set()
        statuses = sorted(queue.get(timeout=30) for _ in processes)
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        queue.close()
    assert statuses == (["OK", "OK"] if identical else ["CONFLICT", "OK"])
    assert read(tmp_path).entry_count == 1
    for directory in ("records", "slots", "manifest"):
        assert len(list((tmp_path / "NIFTY" / SESSION / directory).iterdir())) == 1


def test_concurrent_distinct_slots_preserve_all_records(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(
            lambda minute: capture(tmp_path, stamp=STAMP + timedelta(minutes=minute)),
            range(8),
        ))
    assert read(tmp_path).entry_count == 8
    expected = {_paths(tmp_path, entry)["record"] for entry in entries}
    assert set((tmp_path / "NIFTY" / SESSION / "records").iterdir()) == expected
