
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from services.brain import snapshot_journal_v1 as journal
from services.brain.market_snapshot_v1 import (
    build_market_snapshot_v1,
)
from services.brain.snapshot_journal_v1 import (
    SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1,
    SnapshotJournalConflictError,
    SnapshotJournalDecodeError,
    SnapshotJournalIntegrityError,
    SnapshotJournalVerificationV1,
    capture_snapshot_v1,
    enumerate_snapshot_journal_v1,
    replay_snapshot_journal_v1,
    verify_snapshot_journal_v1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxEventRiskSourceV1,
    McxNativeSourceV1,
    adapt_index_breadth_v1,
    adapt_index_news_v1,
    adapt_index_option_chain_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_event_risk_v1,
    adapt_mcx_native_v1,
)


NOW = datetime(
    2026,
    9,
    30,
    10,
    0,
    tzinfo=timezone.utc,
)


def _index_results(
    timestamp=NOW,
    pcr=0.30,
):
    return (
        *adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market="NIFTY",
                observed_at=timestamp,
                generated_at=timestamp,
                previous_session_date="2026-09-29",
                previous_close=22716.20,
                global_bias="BULLISH",
                vix_value=12.4,
                combined_net=-3027.51,
                flow_direction="BEARISH",
                event_status="UNVERIFIED",
                event_source_authoritative=False,
            )
        ),

        adapt_index_news_v1(
            IndexNewsSourceV1(
                market="NIFTY",
                observed_at=timestamp,
                generated_at=timestamp,
                status="DEGRADED",
                freshness="FRESH",
                source="LEGACY_NEWS_ENGINE",
                sentiment="BULLISH",
                direction="BULLISH",
                bullish_count=5,
                bearish_count=1,
                headline_count=20,
                feeds_available=2,
                feeds_expected=3,
            )
        ),

        *adapt_index_technical_v1(
            IndexTechnicalSourceV1(
                market="NIFTY",
                observed_at=timestamp,
                generated_at=timestamp,
                mtf_direction="BULLISH",
                rsi=57.0,
                rsi_direction="BULLISH",
                adx=25.0,
                regime="TRENDING",
            )
        ),

        adapt_index_breadth_v1(
            IndexBreadthSourceV1(
                market="NIFTY",
                observed_at=timestamp,
                generated_at=timestamp,
                breadth_score=0.30,
                breadth_direction="BULLISH",
            )
        ),

        adapt_index_option_chain_v1(
            IndexOptionChainSourceV1(
                market="NIFTY",
                observed_at=timestamp,
                generated_at=timestamp,
                pcr_value=pcr,
                pcr_direction="BULLISH",
                pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
                max_pain=22700.0,
            )
        ),
    )


def _index_snapshot(
    timestamp=NOW,
    pcr=0.30,
    results=None,
):
    if results is None:
        results = _index_results(
            timestamp,
            pcr,
        )

    return build_market_snapshot_v1(
        market="NIFTY",
        snapshot_at=timestamp,
        generated_at=timestamp,
        analyzer_results=results,
        source_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        source_policy_epoch="NS_CERT_20260929_V4",
        source_runtime_ref="R2.2",
    )


def _mcx_snapshot(
    timestamp=NOW,
):
    results = (
        *adapt_mcx_native_v1(
            McxNativeSourceV1(
                market="CRUDEOILM",
                observed_at=timestamp,
                generated_at=timestamp,
            )
        ),

        adapt_mcx_event_risk_v1(
            McxEventRiskSourceV1(
                market="CRUDEOILM",
                observed_at=timestamp,
                generated_at=timestamp,
            )
        ),
    )

    return build_market_snapshot_v1(
        market="CRUDEOILM",
        snapshot_at=timestamp,
        generated_at=timestamp,
        analyzer_results=results,
        source_strategy_version="MCX_POST_PRECISION_V5",
        source_policy_epoch="POST_PRECISION_V5",
        source_runtime_ref="R2.2",
    )


def _session_root(
    root,
    market="NIFTY",
):
    return (
        root
        / market
        / "2026-09-30"
    )


def _manifest_files(
    root,
    market="NIFTY",
):
    return sorted(
        (
            _session_root(
                root,
                market,
            )
            / "manifest"
        ).glob(
            "*.json"
        )
    )


def _slot_files(
    root,
    market="NIFTY",
):
    return sorted(
        (
            _session_root(
                root,
                market,
            )
            / "slots"
        ).glob(
            "*.json"
        )
    )


def _record_files(
    root,
    market="NIFTY",
):
    return sorted(
        (
            _session_root(
                root,
                market,
            )
            / "records"
        ).glob(
            "*.json"
        )
    )


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    )


def test_capture_structure_and_identical_idempotency(
    tmp_path,
):
    snapshot = _index_snapshot()

    first = capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
    )

    second = capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
    )

    assert first == second
    assert len(_record_files(tmp_path)) == 1
    assert len(_slot_files(tmp_path)) == 1
    assert len(_manifest_files(tmp_path)) == 1


def test_same_slot_different_snapshot_is_rejected(
    tmp_path,
):
    first = _index_snapshot(
        pcr=0.30
    )

    second = _index_snapshot(
        pcr=0.31
    )

    assert first.snapshot_at == second.snapshot_at
    assert first.snapshot_sha256 != second.snapshot_sha256

    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=first,
    )

    with pytest.raises(
        SnapshotJournalConflictError,
    ):
        capture_snapshot_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=second,
        )

    entries = enumerate_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    assert len(entries) == 1
    assert entries[0].snapshot_sha256 == first.snapshot_sha256


def test_chronological_enumeration_verification_and_replay(
    tmp_path,
):
    first = _index_snapshot(
        NOW,
        0.30,
    )

    second = _index_snapshot(
        NOW + timedelta(minutes=1),
        0.31,
    )

    third = _index_snapshot(
        NOW + timedelta(minutes=2),
        0.32,
    )

    for snapshot in (
        third,
        first,
        second,
    ):
        capture_snapshot_v1(
            journal_root=tmp_path,
            session_id="2026-09-30",
            snapshot=snapshot,
        )

    entries = enumerate_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    verification = verify_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )

    assert [
        item.snapshot_sha256
        for item in entries
    ] == [
        first.snapshot_sha256,
        second.snapshot_sha256,
        third.snapshot_sha256,
    ]

    assert [
        item.snapshot_sha256
        for item in replayed
    ] == [
        first.snapshot_sha256,
        second.snapshot_sha256,
        third.snapshot_sha256,
    ]

    assert verification.entry_count == 3
    assert verification.chronological is True
    assert verification.first_snapshot_at == first.snapshot_at
    assert verification.last_snapshot_at == third.snapshot_at


def test_manifest_hash_tamper_is_detected(
    tmp_path,
):
    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    path = _manifest_files(
        tmp_path
    )[0]

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "source_runtime_ref"
    ] = "TAMPERED"

    path.write_text(
        _canonical(
            payload
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="SHA-256",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_duplicate_manifest_key_is_rejected(
    tmp_path,
):
    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    path = _manifest_files(
        tmp_path
    )[0]

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
        SnapshotJournalDecodeError,
        match="duplicate JSON object key",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_slot_tamper_is_detected(
    tmp_path,
):
    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    path = _slot_files(
        tmp_path
    )[0]

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "snapshot_sha256"
    ] = "0" * 64

    path.write_text(
        _canonical(
            payload
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="slot",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_snapshot_record_tamper_is_detected(
    tmp_path,
):
    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    path = _record_files(
        tmp_path
    )[0]

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "snapshot_payload"
    ][
        "source_runtime_ref"
    ] = "TAMPERED"

    path.write_text(
        _canonical(
            payload
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="replay",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_missing_record_and_missing_slot_are_detected(
    tmp_path,
):
    record_root = (
        tmp_path
        / "record-case"
    )

    capture_snapshot_v1(
        journal_root=record_root,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    _record_files(
        record_root
    )[0].unlink()

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="missing snapshot record",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=record_root,
            market="NIFTY",
            session_id="2026-09-30",
        )


    slot_root = (
        tmp_path
        / "slot-case"
    )

    capture_snapshot_v1(
        journal_root=slot_root,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    _slot_files(
        slot_root
    )[0].unlink()

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="no slot claim",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=slot_root,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_record_relpath_escape_is_rejected_even_when_entry_rehashed(
    tmp_path,
):
    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=_index_snapshot(),
    )

    path = _manifest_files(
        tmp_path
    )[0]

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "record_relpath"
    ] = "../escape.json"

    unhashed = {
        key:
            value
        for key, value in payload.items()
        if key != "entry_sha256"
    }

    payload[
        "entry_sha256"
    ] = sha256(
        _canonical(
            unhashed
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    path.write_text(
        _canonical(
            payload
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SnapshotJournalIntegrityError,
        match="record_relpath",
    ):
        enumerate_snapshot_journal_v1(
            journal_root=tmp_path,
            market="NIFTY",
            session_id="2026-09-30",
        )


def test_source_identity_and_zero_authority_survive_journal(
    tmp_path,
):
    snapshot = _index_snapshot()

    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
    )

    entry = enumerate_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )[0]

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id="2026-09-30",
    )[0]

    assert (
        entry.source_strategy_version
        == "NS_DESIGN_B_BID_AUTH_V4"
    )

    assert (
        entry.source_policy_epoch
        == "NS_CERT_20260929_V4"
    )

    assert entry.source_runtime_ref == "R2.2"

    assert replayed.execution_authority is False
    assert replayed.decision_authority is False
    assert replayed.risk_authority is False
    assert replayed.position_authority is False
    assert replayed.certification_authority is False


def test_mcx_capture_and_replay(
    tmp_path,
):
    snapshot = _mcx_snapshot()

    capture_snapshot_v1(
        journal_root=tmp_path,
        session_id="2026-09-30",
        snapshot=snapshot,
    )

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="CRUDEOILM",
        session_id="2026-09-30",
    )

    assert len(replayed) == 1
    assert replayed[0].snapshot_sha256 == snapshot.snapshot_sha256
    assert replayed[0].production_complete is True


def test_verification_schema_is_enforced():
    with pytest.raises(
        ValueError,
        match="verification schema",
    ):
        SnapshotJournalVerificationV1(
            market="NIFTY",
            session_id="2026-09-30",
            entry_count=0,
            snapshot_sha256s=(),
            first_snapshot_at=None,
            last_snapshot_at=None,
            chronological=True,
            schema_version="BRAIN_SNAPSHOT_JOURNAL_VERIFICATION_V2",
        )

    valid = SnapshotJournalVerificationV1(
        market="NIFTY",
        session_id="2026-09-30",
        entry_count=0,
        snapshot_sha256s=(),
        first_snapshot_at=None,
        last_snapshot_at=None,
        chronological=True,
        schema_version=(
            SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1
        ),
    )

    assert valid.entry_count == 0


def test_invalid_session_id_is_rejected(
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="YYYY-MM-DD",
    ):
        capture_snapshot_v1(
            journal_root=tmp_path,
            session_id="30-09-2026",
            snapshot=_index_snapshot(),
        )


def test_immutable_publish_concurrent_different_bytes_rejected(
    tmp_path,
    monkeypatch,
):
    target = (
        tmp_path
        / "entry.json"
    )

    requested = b"FIRST\n"
    competing = b"SECOND\n"

    real_link = journal.os.link

    injected = {
        "done":
            False,
    }


    def competing_link(
        source,
        destination,
    ):
        if not injected[
            "done"
        ]:
            injected[
                "done"
            ] = True

            Path(
                destination
            ).write_bytes(
                competing
            )

        return real_link(
            source,
            destination,
        )


    monkeypatch.setattr(
        journal.os,
        "link",
        competing_link,
    )


    with pytest.raises(
        SnapshotJournalConflictError,
    ):
        journal._publish_immutable(
            target,
            requested,
        )


    assert target.read_bytes() == competing


def test_immutable_publish_concurrent_identical_bytes_is_idempotent(
    tmp_path,
    monkeypatch,
):
    target = (
        tmp_path
        / "entry.json"
    )

    requested = b"SAME\n"

    real_link = journal.os.link

    injected = {
        "done":
            False,
    }


    def competing_link(
        source,
        destination,
    ):
        if not injected[
            "done"
        ]:
            injected[
                "done"
            ] = True

            Path(
                destination
            ).write_bytes(
                requested
            )

        return real_link(
            source,
            destination,
        )


    monkeypatch.setattr(
        journal.os,
        "link",
        competing_link,
    )


    returned = journal._publish_immutable(
        target,
        requested,
    )


    assert returned == target
    assert target.read_bytes() == requested


def test_journal_module_has_no_provider_or_broker_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "snapshot_journal_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
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
                for alias in node.names
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
        "execution",
    )


    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )
