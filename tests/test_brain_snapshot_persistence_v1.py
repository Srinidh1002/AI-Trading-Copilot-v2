from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from services.brain.market_snapshot_v1 import (
    build_market_snapshot_v1,
)
from services.brain.snapshot_persistence_v1 import (
    SNAPSHOT_RECORD_SCHEMA_V1,
    SnapshotIntegrityError,
    SnapshotPersistenceConflictError,
    SnapshotRecordDecodeError,
    SnapshotSchemaError,
    load_snapshot_record_v1,
    persist_snapshot_record_v1,
    replay_snapshot_record_v1,
    serialize_snapshot_record_v1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    adapt_index_breadth_v1,
    adapt_index_news_v1,
    adapt_index_option_chain_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
)


NOW = datetime(
    2026,
    9,
    30,
    9,
    0,
    tzinfo=timezone.utc,
)


def index_results():
    return (
        *adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                previous_session_date="2026-09-29",
                previous_open=22732.45,
                previous_high=22753.25,
                previous_low=22569.65,
                previous_close=22716.20,
                gap_points=12.0,
                gap_pct=0.05,
                gap_direction="BULLISH",
                global_status="AVAILABLE",
                global_freshness="UNKNOWN",
                global_bias="BULLISH",
                global_score=0.60,
                vix_value=12.4,
                vix_regime="LOW",
                flow_direction="BEARISH",
                fii_cash_net=-9980.22,
                dii_cash_net=6952.71,
                combined_net=-3027.51,
                event_status="UNVERIFIED",
                event_freshness="UNKNOWN",
                event_source_authoritative=False,
                event_provider_block_entries=False,
                event_hard_block_eligible=False,
            )
        ),

        adapt_index_news_v1(
            IndexNewsSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
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
                observed_at=NOW,
                generated_at=NOW,
                mtf_direction="BULLISH",
                rsi=57.0,
                rsi_direction="BULLISH",
                adx=25.0,
                adx_direction="BULLISH",
                ema_state="EMA20_ABOVE_EMA50",
                ema_direction="BULLISH",
                macd_state="POSITIVE",
                macd_direction="BULLISH",
                bollinger_state="MID_TO_UPPER",
                bollinger_direction="BULLISH",
                regime="TRENDING",
                regime_direction="BULLISH",
            )
        ),

        adapt_index_breadth_v1(
            IndexBreadthSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                breadth_score=0.30,
                breadth_direction="BULLISH",
                advances=32,
                declines=17,
                unchanged=1,
                heavyweight_direction="MIXED",
            )
        ),

        adapt_index_option_chain_v1(
            IndexOptionChainSourceV1(
                market="NIFTY",
                observed_at=NOW,
                generated_at=NOW,
                pcr_value=0.30,
                pcr_direction="BULLISH",
                pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
                max_pain=22700.0,
                support=22600.0,
                resistance=22800.0,
                atm_strike=22700.0,
                expiry="2026-10-01",
                chain_coverage_pct=100.0,
            )
        ),
    )


def make_snapshot(
    *,
    generated_at=NOW,
    results=None,
):
    if results is None:
        results = index_results()

    return build_market_snapshot_v1(
        market="NIFTY",
        snapshot_at=NOW,
        generated_at=generated_at,
        analyzer_results=results,
        source_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        source_policy_epoch="NS_CERT_20260929_V4",
        source_runtime_ref="R2.2",
    )


def canonical_json(
    value,
):
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


def payload_digest(
    payload,
):
    return sha256(
        canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def encode_record(
    record,
):
    return (
        canonical_json(
            record
        )
        + "\n"
    )


def test_serialize_replay_round_trip_preserves_hash_and_json():
    original = make_snapshot()

    encoded = serialize_snapshot_record_v1(
        original
    )

    replayed = replay_snapshot_record_v1(
        encoded
    )

    assert replayed.snapshot_sha256 == original.snapshot_sha256
    assert replayed.canonical_json() == original.canonical_json()


def test_disk_persistence_round_trip_preserves_hash(
    tmp_path,
):
    snapshot = make_snapshot()

    path = tmp_path / "snapshot.json"

    persist_snapshot_record_v1(
        snapshot,
        path,
    )

    replayed = load_snapshot_record_v1(
        path
    )

    assert replayed.snapshot_sha256 == snapshot.snapshot_sha256
    assert path.is_file()


def test_serialization_is_deterministic():
    snapshot = make_snapshot()

    first = serialize_snapshot_record_v1(
        snapshot
    )

    second = serialize_snapshot_record_v1(
        snapshot
    )

    assert first == second


def test_reordered_equivalent_snapshot_has_identical_record_bytes():
    normal = make_snapshot()

    reversed_snapshot = make_snapshot(
        results=tuple(
            reversed(
                index_results()
            )
        )
    )

    assert (
        serialize_snapshot_record_v1(
            normal
        )
        ==
        serialize_snapshot_record_v1(
            reversed_snapshot
        )
    )


def test_modified_payload_without_hash_update_is_rejected():
    snapshot = make_snapshot()

    record = json.loads(
        serialize_snapshot_record_v1(
            snapshot
        )
    )

    record[
        "snapshot_payload"
    ][
        "source_runtime_ref"
    ] = "TAMPERED"

    with pytest.raises(
        SnapshotIntegrityError,
        match="canonical payload",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_modified_declared_hash_is_rejected():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "snapshot_sha256"
    ] = "0" * 64

    with pytest.raises(
        SnapshotIntegrityError,
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_truncated_record_is_rejected():
    encoded = serialize_snapshot_record_v1(
        make_snapshot()
    )

    truncated = encoded[
        :-50
    ]

    with pytest.raises(
        SnapshotRecordDecodeError,
    ):
        replay_snapshot_record_v1(
            truncated
        )


def test_duplicate_json_keys_are_rejected():
    encoded = serialize_snapshot_record_v1(
        make_snapshot()
    )

    duplicated = encoded.replace(
        '"record_schema_version":',
        (
            '"record_schema_version":"DUPLICATE",'
            '"record_schema_version":'
        ),
        1,
    )

    with pytest.raises(
        SnapshotRecordDecodeError,
        match="duplicate JSON object key",
    ):
        replay_snapshot_record_v1(
            duplicated
        )


def test_record_schema_mismatch_is_rejected():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "record_schema_version"
    ] = "BRAIN_SNAPSHOT_RECORD_V2"

    with pytest.raises(
        SnapshotSchemaError,
        match="record_schema_version",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_snapshot_schema_mismatch_is_rejected():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "snapshot_schema_version"
    ] = "BRAIN_MARKET_SNAPSHOT_V2"

    record[
        "snapshot_payload"
    ][
        "schema_version"
    ] = "BRAIN_MARKET_SNAPSHOT_V2"

    record[
        "snapshot_sha256"
    ] = payload_digest(
        record[
            "snapshot_payload"
        ]
    )

    with pytest.raises(
        SnapshotSchemaError,
        match="snapshot_schema_version",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_authority_promotion_is_rejected_even_with_recomputed_hash():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "snapshot_payload"
    ][
        "execution_authority"
    ] = True

    record[
        "snapshot_sha256"
    ] = payload_digest(
        record[
            "snapshot_payload"
        ]
    )

    with pytest.raises(
        SnapshotSchemaError,
        match="execution_authority",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_invalid_sha_format_is_rejected():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "snapshot_sha256"
    ] = "NOT-A-SHA"

    with pytest.raises(
        SnapshotSchemaError,
        match="snapshot_sha256",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_extra_envelope_field_is_rejected():
    record = json.loads(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    record[
        "unexpected"
    ] = "value"

    with pytest.raises(
        SnapshotSchemaError,
        match="keys mismatch",
    ):
        replay_snapshot_record_v1(
            encode_record(
                record
            )
        )


def test_identical_persist_is_idempotent(
    tmp_path,
):
    snapshot = make_snapshot()

    path = tmp_path / "snapshot.json"

    first = persist_snapshot_record_v1(
        snapshot,
        path,
    )

    bytes_before = path.read_bytes()

    second = persist_snapshot_record_v1(
        snapshot,
        path,
    )

    bytes_after = path.read_bytes()

    assert first == second
    assert bytes_before == bytes_after


def test_conflicting_existing_record_is_rejected(
    tmp_path,
):
    path = tmp_path / "snapshot.json"

    first = make_snapshot()

    second = make_snapshot(
        generated_at=NOW
        + timedelta(
            seconds=1
        )
    )

    persist_snapshot_record_v1(
        first,
        path,
    )

    with pytest.raises(
        SnapshotPersistenceConflictError,
    ):
        persist_snapshot_record_v1(
            second,
            path,
        )


def test_partial_snapshot_replays_missing_coverage():
    results = tuple(
        result
        for result in index_results()
        if result.analyzer
        != "index.news.legacy_v1"
    )

    original = make_snapshot(
        results=results
    )

    replayed = replay_snapshot_record_v1(
        serialize_snapshot_record_v1(
            original
        )
    )

    assert replayed.production_complete is False

    assert replayed.missing_production_analyzers == (
        "index.news.legacy_v1",
    )

    assert (
        replayed.production_coverage_pct
        == original.production_coverage_pct
    )


def test_unverified_and_unknown_freshness_survive_replay():
    replayed = replay_snapshot_record_v1(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    assert (
        replayed.evidence_status_counts()[
            "UNVERIFIED"
        ]
        >= 1
    )

    assert (
        replayed.freshness_counts()[
            "UNKNOWN"
        ]
        >= 1
    )


def test_option_metadata_survives_round_trip():
    replayed = replay_snapshot_record_v1(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    option_result = next(
        result
        for result in replayed.analyzer_results
        if result.analyzer
        == "index.option_chain.legacy_v1"
    )

    pcr = next(
        evidence
        for evidence in option_result.evidence
        if evidence.feature
        == "PCR"
    )

    metadata = dict(
        pcr.metadata
    )

    assert metadata[
        "source_interpretation"
    ] == "INDEX_LEGACY_SOURCE_RULE"

    assert metadata[
        "chain_coverage_pct"
    ] == 100.0



def test_late_conflicting_writer_cannot_be_overwritten(
    tmp_path,
    monkeypatch,
):
    """A competing writer winning after temp creation must not be replaced."""

    from services.brain import snapshot_persistence_v1 as module

    first = make_snapshot()

    second = make_snapshot(
        generated_at=NOW
        + timedelta(
            seconds=1
        )
    )

    target = tmp_path / "snapshot.json"

    competing_bytes = serialize_snapshot_record_v1(
        second
    ).encode(
        "utf-8"
    )


    real_link = module.os.link

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
                competing_bytes
            )

        return real_link(
            source,
            destination,
        )


    monkeypatch.setattr(
        module.os,
        "link",
        competing_link,
    )


    with pytest.raises(
        SnapshotPersistenceConflictError,
    ):
        persist_snapshot_record_v1(
            first,
            target,
        )


    assert target.read_bytes() == competing_bytes

    replayed = load_snapshot_record_v1(
        target
    )

    assert replayed.snapshot_sha256 == second.snapshot_sha256


def test_late_identical_writer_is_idempotent(
    tmp_path,
    monkeypatch,
):
    """A competing identical writer is treated as successful idempotency."""

    from services.brain import snapshot_persistence_v1 as module

    snapshot = make_snapshot()

    target = tmp_path / "snapshot.json"

    identical_bytes = serialize_snapshot_record_v1(
        snapshot
    ).encode(
        "utf-8"
    )


    real_link = module.os.link

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
                identical_bytes
            )

        return real_link(
            source,
            destination,
        )


    monkeypatch.setattr(
        module.os,
        "link",
        competing_link,
    )


    returned = persist_snapshot_record_v1(
        snapshot,
        target,
    )


    assert returned == target
    assert target.read_bytes() == identical_bytes


def test_persistence_module_has_no_provider_or_broker_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "snapshot_persistence_v1.py"
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


def test_replayed_snapshot_remains_zero_authority():
    replayed = replay_snapshot_record_v1(
        serialize_snapshot_record_v1(
            make_snapshot()
        )
    )

    assert replayed.execution_authority is False
    assert replayed.decision_authority is False
    assert replayed.risk_authority is False
    assert replayed.position_authority is False
    assert replayed.certification_authority is False