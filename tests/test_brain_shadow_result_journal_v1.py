from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from hashlib import sha256
import json
from pathlib import Path
from threading import Barrier

import pytest

from services.brain.market_snapshot_v1 import (
    build_market_snapshot_v1,
)
from services.brain.shadow_composer_v1 import (
    compose_shadow_brain_v1,
)
from services.brain.shadow_result_journal_v1 import (
    ShadowResultJournalConflictError,
    ShadowResultJournalIntegrityError,
    ShadowResultJournalSchemaError,
    capture_shadow_result_journal_v1,
    enumerate_shadow_result_journal_v1,
    replay_shadow_result_journal_v1,
    shadow_result_journal_slot_id_v1,
    verify_shadow_result_journal_v1,
)


STAMP = datetime(
    2026,
    9,
    30,
    12,
    0,
    tzinfo=timezone.utc,
)


MARKETS = (
    "NIFTY",
    "SENSEX",
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


def _snapshot(
    market="NIFTY",
    *,
    stamp=STAMP,
    runtime="STEP6G_RUNTIME",
    strategy="STEP6G_STRATEGY",
    policy="STEP6G_EPOCH",
):
    return build_market_snapshot_v1(
        market=market,
        snapshot_at=stamp,
        generated_at=stamp,
        analyzer_results=(),
        source_strategy_version=strategy,
        source_policy_epoch=policy,
        source_runtime_ref=runtime,
    )


def _pair(
    market="NIFTY",
    **kwargs,
):
    snapshot = _snapshot(
        market,
        **kwargs,
    )

    result = compose_shadow_brain_v1(
        snapshot
    )

    return (
        snapshot,
        result,
    )


def _canonical(
    value,
):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
        allow_nan=False,
    )


def _rehash_without(
    document,
    hash_field,
):
    body = {
        key:
            value
        for key, value
        in document.items()
        if key != hash_field
    }

    document[
        hash_field
    ] = sha256(
        _canonical(
            body
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _paths(
    root,
    entry,
):
    session_root = (
        Path(
            root
        )
        / entry.market
        / entry.session_id
    )

    return {
        "root":
            session_root,
        "record":
            session_root
            / entry.record_relpath,
        "slot":
            session_root
            / "slots"
            / (
                entry.slot_id
                + ".json"
            ),
        "manifest":
            session_root
            / "manifest"
            / (
                entry.slot_id
                + ".json"
            ),
    }


def test_slot_id_is_deterministic():
    first = shadow_result_journal_slot_id_v1(
        market="NIFTY",
        session_id="2026-09-30",
        snapshot_at=STAMP,
    )

    second = shadow_result_journal_slot_id_v1(
        market="NIFTY",
        session_id="2026-09-30",
        snapshot_at=STAMP,
    )

    assert first == second
    assert len(first) == 64


@pytest.mark.parametrize(
    "change",
    (
        "market",
        "session",
        "time",
    ),
)
def test_slot_identity_changes_when_slot_identity_component_changes(
    change,
):
    kwargs = {
        "market":
            "NIFTY",
        "session_id":
            "2026-09-30",
        "snapshot_at":
            STAMP,
    }

    baseline = (
        shadow_result_journal_slot_id_v1(
            **kwargs
        )
    )

    if change == "market":
        kwargs[
            "market"
        ] = "SENSEX"

    elif change == "session":
        kwargs[
            "session_id"
        ] = "2026-10-01"

    elif change == "time":
        kwargs[
            "snapshot_at"
        ] = (
            STAMP
            + timedelta(
                minutes=1
            )
        )

    assert (
        shadow_result_journal_slot_id_v1(
            **kwargs
        )
        != baseline
    )


def test_capture_creates_record_slot_and_manifest(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    paths = _paths(
        tmp_path,
        entry,
    )

    assert paths[
        "record"
    ].is_file()

    assert paths[
        "slot"
    ].is_file()

    assert paths[
        "manifest"
    ].is_file()


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_all_five_markets_capture_replay_exact(
    tmp_path,
    market,
):
    snapshot, result = _pair(
        market
    )

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    entries = enumerate_shadow_result_journal_v1(
        journal_root=tmp_path,
        market=market,
        session_id="2026-09-30",
    )

    replayed = replay_shadow_result_journal_v1(
        journal_root=tmp_path,
        market=market,
        session_id="2026-09-30",
    )

    assert entries == (
        entry,
    )

    assert replayed == (
        result,
    )

    assert (
        replayed[
            0
        ].snapshot_sha256
        == snapshot.snapshot_sha256
    )


def test_identical_capture_is_idempotent(
    tmp_path,
):
    snapshot, result = _pair()

    first = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    paths = _paths(
        tmp_path,
        first,
    )

    before = {
        name:
            path.read_bytes()
        for name, path
        in paths.items()
        if name
        != "root"
    }

    second = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    after = {
        name:
            path.read_bytes()
        for name, path
        in paths.items()
        if name
        != "root"
    }

    assert second == first
    assert after == before


def test_same_slot_different_snapshot_is_conflict(
    tmp_path,
):
    first_snapshot, first_result = _pair(
        runtime="STEP6G_FIRST"
    )

    second_snapshot, second_result = _pair(
        runtime="STEP6G_SECOND"
    )

    capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=first_snapshot,
        result=first_result,
    )

    with pytest.raises(
        ShadowResultJournalConflictError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=second_snapshot,
            result=second_result,
        )


def test_same_snapshot_same_slot_different_result_is_conflict(
    tmp_path,
):
    snapshot, result = _pair()

    different_result = replace(
        result,
        stale_evidence_ids=(
            "journal-test-stale",
        ),
    )

    capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    with pytest.raises(
        ShadowResultJournalConflictError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=different_result,
        )


def test_same_snapshot_different_session_is_allowed(
    tmp_path,
):
    snapshot, result = _pair()

    first = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    second = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-10-01",
        snapshot=snapshot,
        result=result,
    )

    assert first.session_id != second.session_id
    assert first.slot_id != second.slot_id


def test_enumeration_is_chronological(
    tmp_path,
):
    expected = []

    for minute in (
        2,
        0,
        1,
    ):
        stamp = (
            STAMP
            + timedelta(
                minutes=minute
            )
        )

        snapshot, result = _pair(
            stamp=stamp,
            runtime=f"runtime-{minute}",
        )

        expected.append(
            (
                stamp,
                result,
            )
        )

        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=result,
        )

    entries = enumerate_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    assert tuple(
        entry.snapshot_at
        for entry
        in entries
    ) == tuple(
        sorted(
            stamp
            for stamp, _
            in expected
        )
    )


def test_replay_is_chronological_and_exact(
    tmp_path,
):
    pairs = []

    for minute in (
        1,
        0,
        2,
    ):
        snapshot, result = _pair(
            stamp=(
                STAMP
                + timedelta(
                    minutes=minute
                )
            ),
            runtime=f"replay-{minute}",
        )

        pairs.append(
            (
                snapshot,
                result,
            )
        )

        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=result,
        )

    replayed = replay_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    expected = tuple(
        result
        for snapshot, result
        in sorted(
            pairs,
            key=lambda item:
                item[
                    0
                ].snapshot_at,
        )
    )

    assert replayed == expected


def test_verification_reports_exact_count_and_integrity(
    tmp_path,
):
    for minute in range(
        3
    ):
        snapshot, result = _pair(
            stamp=(
                STAMP
                + timedelta(
                    minutes=minute
                )
            ),
            runtime=f"verify-{minute}",
        )

        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=result,
        )

    verification = verify_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    assert verification.entry_count == 3
    assert verification.chronological is True
    assert verification.manifest_hashes_verified is True
    assert verification.slot_hashes_verified is True
    assert verification.records_verified is True


def test_empty_journal_enumerates_empty(
    tmp_path,
):
    assert enumerate_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    ) == ()


def test_empty_journal_replays_empty(
    tmp_path,
):
    assert replay_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    ) == ()


def test_empty_journal_verifies_zero_entries(
    tmp_path,
):
    verification = verify_shadow_result_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    assert verification.entry_count == 0
    assert verification.chronological is True


@pytest.mark.parametrize(
    "session_id",
    (
        "",
        "   ",
        ".",
        "..",
        "../escape",
        "a/b",
        r"a\b",
        "bad session",
    ),
)
def test_unsafe_session_id_is_rejected(
    tmp_path,
    session_id,
):
    snapshot, result = _pair()

    with pytest.raises(
        ShadowResultJournalSchemaError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id=session_id,
            snapshot=snapshot,
            result=result,
        )


def test_snapshot_result_market_mismatch_is_rejected(
    tmp_path,
):
    snapshot = _snapshot(
        "NIFTY"
    )

    other_snapshot = _snapshot(
        "SENSEX"
    )

    result = compose_shadow_brain_v1(
        other_snapshot
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=result,
        )


def test_snapshot_hash_mismatch_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    forged = replace(
        result,
        snapshot_sha256=(
            "0"
            * 64
        ),
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=forged,
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    (
        (
            "source_strategy_version",
            "OTHER_STRATEGY",
        ),
        (
            "source_policy_epoch",
            "OTHER_EPOCH",
        ),
        (
            "source_runtime_ref",
            "OTHER_RUNTIME",
        ),
    ),
)
def test_provenance_mismatch_is_rejected(
    tmp_path,
    field_name,
    value,
):
    snapshot, result = _pair()

    forged = replace(
        result,
        **{
            field_name:
                value
        },
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=forged,
        )


def test_generated_at_mismatch_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    forged = replace(
        result,
        generated_at=(
            result.generated_at
            + timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=forged,
        )


def test_slot_tamper_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "slot"
    ]

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    document[
        "snapshot_sha256"
    ] = (
        "0"
        * 64
    )

    path.write_text(
        _canonical(
            document
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_manifest_tamper_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "manifest"
    ]

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    document[
        "slot_sha256"
    ] = (
        "0"
        * 64
    )

    path.write_text(
        _canonical(
            document
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_missing_record_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    _paths(
        tmp_path,
        entry,
    )[
        "record"
    ].unlink()

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        replay_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_missing_slot_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    _paths(
        tmp_path,
        entry,
    )[
        "slot"
    ].unlink()

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_missing_manifest_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    _paths(
        tmp_path,
        entry,
    )[
        "manifest"
    ].unlink()

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_tampered_record_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "record"
    ]

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    document[
        "shadow_result_payload"
    ][
        "source_runtime_ref"
    ] = "TAMPERED"

    path.write_text(
        _canonical(
            document
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        replay_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_duplicate_slot_json_key_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "slot"
    ]

    text = path.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"market":"NIFTY"',
        '"market":"NIFTY","market":"NIFTY"',
        1,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="duplicate JSON object key",
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_nonfinite_manifest_json_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "manifest"
    ]

    text = path.read_text(
        encoding="utf-8"
    )

    prefix = '"manifest_sha256":"'

    start = text.index(
        prefix
    )

    value_start = (
        start
        + len(
            prefix
        )
    )

    value_end = text.index(
        '"',
        value_start,
    )

    text = (
        text[
            :start
        ]
        + '"manifest_sha256":NaN'
        + text[
            value_end
            + 1:
        ]
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="non-finite",
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_manifest_path_cross_binding_is_rejected_even_with_valid_manifest_hash(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    path = _paths(
        tmp_path,
        entry,
    )[
        "manifest"
    ]

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    document[
        "record_relpath"
    ] = "../escape.json"

    _rehash_without(
        document,
        "manifest_sha256",
    )

    path.write_text(
        _canonical(
            document
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_unexpected_slot_artifact_is_rejected(
    tmp_path,
):
    snapshot, result = _pair()

    entry = capture_shadow_result_journal_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
        result=result,
    )

    slot_dir = _paths(
        tmp_path,
        entry,
    )[
        "slot"
    ].parent

    (
        slot_dir
        / "unexpected.tmp"
    ).write_text(
        "x",
        encoding="utf-8",
    )

    with pytest.raises(
        ShadowResultJournalIntegrityError
    ):
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_concurrent_identical_capture_is_idempotent(
    tmp_path,
):
    snapshot, result = _pair()

    workers = 6

    barrier = Barrier(
        workers
    )

    def worker():
        barrier.wait()

        return capture_shadow_result_journal_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
            result=result,
        )

    with ThreadPoolExecutor(
        max_workers=workers
    ) as pool:

        futures = [
            pool.submit(
                worker
            )
            for _ in range(
                workers
            )
        ]

        entries = tuple(
            future.result()
            for future
            in futures
        )

    assert len(
        entries
    ) == workers

    assert len(
        set(
            entries
        )
    ) == 1

    assert len(
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )
    ) == 1


def test_concurrent_different_capture_same_slot_is_conflict_safe(
    tmp_path,
):
    first_snapshot, first_result = _pair(
        runtime="CONCURRENT_FIRST"
    )

    second_snapshot, second_result = _pair(
        runtime="CONCURRENT_SECOND"
    )

    barrier = Barrier(
        2
    )

    def worker(
        snapshot,
        result,
    ):
        barrier.wait()

        try:
            capture_shadow_result_journal_v1(
                journal_root=tmp_path,
                session_id="2026-09-30",
                snapshot=snapshot,
                result=result,
            )

            return "OK"

        except ShadowResultJournalConflictError:
            return "CONFLICT"

    with ThreadPoolExecutor(
        max_workers=2
    ) as pool:

        first_future = pool.submit(
            worker,
            first_snapshot,
            first_result,
        )

        second_future = pool.submit(
            worker,
            second_snapshot,
            second_result,
        )

        statuses = sorted(
            (
                first_future.result(),
                second_future.result(),
            )
        )

    assert statuses == [
        "CONFLICT",
        "OK",
    ]

    assert len(
        enumerate_shadow_result_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )
    ) == 1


def test_journal_not_exported_from_services_brain_package_yet():
    import services.brain as brain

    assert not hasattr(
        brain,
        "capture_shadow_result_journal_v1",
    )

    assert not hasattr(
        brain,
        "verify_shadow_result_journal_v1",
    )


def test_module_has_no_provider_broker_b3_or_composer_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_journal_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imports = []

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name.lower()
                for alias
                in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imports.append(
                (
                    node.module
                    or ""
                ).lower()
            )

    forbidden = (
        "fyers",
        "smartapi",
        "requests",
        "yfinance",
        "broker",
        "paper_orchestration",
        "capture_coordinator",
        "snapshot_persistence_v1",
        "snapshot_journal_v1",
        "shadow_composer_v1",
    )

    assert not any(
        token in module
        for module
        in imports
        for token
        in forbidden
    )


def test_module_has_no_clock_random_trade_pnl_or_certification_surface():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_journal_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "random.",
        "buy_call",
        "buy_put",
        "strike_selection",
        "quantity_selection",
        "stop_loss",
        "target_1",
        "target_2",
        "target_3",
        "profit_factor",
        "win_rate",
        "pnl",
        "certification_counter",
        "submit_order",
    )

    assert not any(
        token in source
        for token
        in forbidden
    )


def test_module_contains_immutable_publication_and_hash_primitives():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_journal_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    assert "os.fsync(" in source
    assert "os.link(" in source
    assert "NamedTemporaryFile" in source
    assert "object_pairs_hook" in source
    assert "parse_constant" in source
    assert "shadow_result_sha256" in source
    assert "snapshot_sha256" in source


def test_module_depends_on_frozen_shadow_result_persistence():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_journal_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    assert (
        "services.brain.shadow_result_persistence_v1"
        in source
    )

    assert (
        "persist_shadow_result_record_v1"
        in source
    )

    assert (
        "load_shadow_result_record_v1"
        in source
    )
