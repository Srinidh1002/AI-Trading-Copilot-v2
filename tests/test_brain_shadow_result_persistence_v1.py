from __future__ import annotations

import ast
from dataclasses import (
    fields,
    replace,
)
from datetime import (
    datetime,
    timezone,
)
import json
from pathlib import Path

import pytest

from services.brain.market_snapshot_v1 import (
    build_market_snapshot_v1,
)
from services.brain.shadow_brain_v1 import (
    ShadowBrainResultV1,
    ShadowHypothesisV1,
)
from services.brain.shadow_composer_v1 import (
    compose_shadow_brain_v1,
)
from services.brain.shadow_result_persistence_v1 import (
    SHADOW_RESULT_RECORD_SCHEMA_V1,
    ShadowResultIntegrityError,
    ShadowResultPersistenceConflictError,
    ShadowResultPersistenceError,
    ShadowResultRecordDecodeError,
    ShadowResultReplayError,
    ShadowResultSchemaError,
    load_shadow_result_record_v1,
    persist_shadow_result_record_v1,
    replay_shadow_result_record_v1,
    serialize_shadow_result_record_v1,
    shadow_result_record_v1,
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


TOP_LEVEL_KEYS = {
    "record_schema_version",
    "shadow_result_schema_version",
    "shadow_result_sha256",
    "snapshot_sha256",
    "shadow_result_payload",
}


def _result(
    market="NIFTY",
):
    snapshot = build_market_snapshot_v1(
        market=market,
        snapshot_at=STAMP,
        generated_at=STAMP,
        analyzer_results=(),
        source_strategy_version="STEP6C_STRATEGY",
        source_policy_epoch="STEP6C_EPOCH",
        source_runtime_ref="STEP6C_RUNTIME",
    )

    return compose_shadow_brain_v1(
        snapshot
    )


def _record_dict(
    result=None,
):
    if result is None:
        result = _result()

    return json.loads(
        serialize_shadow_result_record_v1(
            result
        )
    )


def _json(
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


def _forge_result(
    source,
    **changes,
):
    forged = object.__new__(
        ShadowBrainResultV1
    )

    for field in fields(
        ShadowBrainResultV1
    ):
        object.__setattr__(
            forged,
            field.name,
            changes.get(
                field.name,
                getattr(
                    source,
                    field.name,
                ),
            ),
        )

    return forged


def _forge_hypothesis(
    source,
    **changes,
):
    forged = object.__new__(
        ShadowHypothesisV1
    )

    for field in fields(
        ShadowHypothesisV1
    ):
        object.__setattr__(
            forged,
            field.name,
            changes.get(
                field.name,
                getattr(
                    source,
                    field.name,
                ),
            ),
        )

    return forged


def test_record_has_exact_top_level_schema():
    result = _result()

    record = shadow_result_record_v1(
        result
    )

    assert set(
        record
    ) == TOP_LEVEL_KEYS

    assert (
        record[
            "record_schema_version"
        ]
        == SHADOW_RESULT_RECORD_SCHEMA_V1
    )

    assert (
        record[
            "shadow_result_schema_version"
        ]
        == result.schema_version
    )


def test_record_declared_identity_matches_result():
    result = _result()

    record = shadow_result_record_v1(
        result
    )

    assert (
        record[
            "shadow_result_sha256"
        ]
        == result.shadow_result_sha256
    )

    assert (
        record[
            "snapshot_sha256"
        ]
        == result.snapshot_sha256
    )


def test_record_payload_cross_binds_snapshot_sha256():
    result = _result()

    record = shadow_result_record_v1(
        result
    )

    assert (
        record[
            "snapshot_sha256"
        ]
        == record[
            "shadow_result_payload"
        ][
            "snapshot_sha256"
        ]
    )


def test_serialize_is_deterministic():
    result = _result()

    first = serialize_shadow_result_record_v1(
        result
    )

    second = serialize_shadow_result_record_v1(
        result
    )

    assert first == second


@pytest.mark.parametrize(
    "market",
    MARKETS,
)
def test_all_five_zero_coverage_round_trip(
    market,
):
    result = _result(
        market
    )

    replayed = (
        replay_shadow_result_record_v1(
            serialize_shadow_result_record_v1(
                result
            )
        )
    )

    assert replayed == result

    assert (
        replayed.shadow_result_sha256
        == result.shadow_result_sha256
    )

    assert (
        replayed.snapshot_sha256
        == result.snapshot_sha256
    )

    assert replayed.production_complete is False
    assert replayed.production_coverage_pct == 0.0


def test_replay_round_trip_exact():
    result = _result(
        "GOLDM"
    )

    text = serialize_shadow_result_record_v1(
        result
    )

    replayed = replay_shadow_result_record_v1(
        text
    )

    assert replayed == result
    assert replayed.canonical_json() == result.canonical_json()


def test_load_round_trip_exact(
    tmp_path,
):
    result = _result(
        "CRUDEOILM"
    )

    path = (
        tmp_path
        / "result.json"
    )

    persist_shadow_result_record_v1(
        result,
        path,
    )

    replayed = load_shadow_result_record_v1(
        path
    )

    assert replayed == result


def test_persist_creates_parent_directories(
    tmp_path,
):
    result = _result()

    path = (
        tmp_path
        / "a"
        / "b"
        / "result.json"
    )

    persisted = persist_shadow_result_record_v1(
        result,
        path,
    )

    assert persisted == path
    assert path.is_file()


def test_identical_persistence_is_idempotent(
    tmp_path,
):
    result = _result()

    path = (
        tmp_path
        / "result.json"
    )

    first = persist_shadow_result_record_v1(
        result,
        path,
    )

    first_bytes = path.read_bytes()

    second = persist_shadow_result_record_v1(
        result,
        path,
    )

    second_bytes = path.read_bytes()

    assert first == second == path
    assert first_bytes == second_bytes


def test_existing_different_bytes_are_conflict(
    tmp_path,
):
    first = _result()

    second = replace(
        first,
        source_runtime_ref=
            "STEP6C_RUNTIME_DIFFERENT",
    )

    path = (
        tmp_path
        / "result.json"
    )

    persist_shadow_result_record_v1(
        first,
        path,
    )

    original = path.read_bytes()

    with pytest.raises(
        ShadowResultPersistenceConflictError
    ):
        persist_shadow_result_record_v1(
            second,
            path,
        )

    assert path.read_bytes() == original


def test_non_result_input_is_rejected():
    with pytest.raises(
        TypeError,
        match="ShadowBrainResultV1",
    ):
        shadow_result_record_v1(
            object()
        )


@pytest.mark.parametrize(
    "authority_field",
    (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ),
)
def test_true_authority_result_is_rejected_before_persistence(
    authority_field,
):
    result = _result()

    forged = _forge_result(
        result,
        **{
            authority_field:
                True
        },
    )

    with pytest.raises(
        ShadowResultIntegrityError
    ):
        shadow_result_record_v1(
            forged
        )


@pytest.mark.parametrize(
    "case_name",
    (
        "hypothesis_market_mismatch",
        "invalid_hypothesis_label",
        "invalid_hypothesis_confidence",
        "hypothesis_attribution_overlap",
        "blank_runtime_provenance",
        "naive_snapshot_at",
        "coverage_above_100",
        "completion_contradicts_zero_coverage",
        "duplicate_unverified_ids",
    ),
)
def test_forged_constructor_invalid_result_is_rejected_before_serialization(
    case_name,
):
    result = _result()

    if case_name == "hypothesis_market_mismatch":
        forged_hypothesis = _forge_hypothesis(
            result.hypothesis,
            market="SENSEX",
        )

        forged = _forge_result(
            result,
            hypothesis=forged_hypothesis,
        )

    elif case_name == "invalid_hypothesis_label":
        forged_hypothesis = _forge_hypothesis(
            result.hypothesis,
            hypothesis="FORGED_HYPOTHESIS",
        )

        forged = _forge_result(
            result,
            hypothesis=forged_hypothesis,
        )

    elif case_name == "invalid_hypothesis_confidence":
        forged_hypothesis = _forge_hypothesis(
            result.hypothesis,
            confidence=1.5,
        )

        forged = _forge_result(
            result,
            hypothesis=forged_hypothesis,
        )

    elif case_name == "hypothesis_attribution_overlap":
        forged_hypothesis = _forge_hypothesis(
            result.hypothesis,
            supporting_evidence_ids=(
                "same-id",
            ),
            opposing_evidence_ids=(
                "same-id",
            ),
        )

        forged = _forge_result(
            result,
            hypothesis=forged_hypothesis,
        )

    elif case_name == "blank_runtime_provenance":
        forged = _forge_result(
            result,
            source_runtime_ref="   ",
        )

    elif case_name == "naive_snapshot_at":
        forged = _forge_result(
            result,
            snapshot_at=result.snapshot_at.replace(
                tzinfo=None
            ),
        )

    elif case_name == "coverage_above_100":
        forged = _forge_result(
            result,
            production_coverage_pct=101.0,
        )

    elif case_name == "completion_contradicts_zero_coverage":
        forged = _forge_result(
            result,
            production_complete=True,
        )

    elif case_name == "duplicate_unverified_ids":
        forged = _forge_result(
            result,
            unverified_evidence_ids=(
                "duplicate-id",
                "duplicate-id",
            ),
        )

    else:
        raise AssertionError(
            case_name
        )

    with pytest.raises(
        ShadowResultSchemaError
    ):
        serialize_shadow_result_record_v1(
            forged
        )


def test_parent_file_persistence_error_is_normalized(
    tmp_path,
):
    result = _result()

    parent_file = (
        tmp_path
        / "parent-is-file"
    )

    parent_file.write_text(
        "x",
        encoding="utf-8",
    )

    target = (
        parent_file
        / "child.json"
    )

    with pytest.raises(
        ShadowResultPersistenceError
    ):
        persist_shadow_result_record_v1(
            result,
            target,
        )


def test_replay_non_text_is_rejected():
    with pytest.raises(
        ShadowResultRecordDecodeError
    ):
        replay_shadow_result_record_v1(
            123
        )


def test_invalid_json_is_rejected():
    with pytest.raises(
        ShadowResultRecordDecodeError
    ):
        replay_shadow_result_record_v1(
            "{"
        )


def test_duplicate_json_key_is_rejected():
    valid = serialize_shadow_result_record_v1(
        _result()
    )

    duplicate = (
        "{"
        '"record_schema_version":'
        '"BRAIN_SHADOW_RESULT_RECORD_V1",'
        + valid[1:]
    )

    with pytest.raises(
        ShadowResultRecordDecodeError,
        match="duplicate JSON object key",
    ):
        replay_shadow_result_record_v1(
            duplicate
        )


def test_nonfinite_json_is_rejected():
    valid = serialize_shadow_result_record_v1(
        _result()
    )

    assert (
        '"production_coverage_pct":0.0'
        in valid
    )

    tampered = valid.replace(
        '"production_coverage_pct":0.0',
        '"production_coverage_pct":NaN',
        1,
    )

    with pytest.raises(
        ShadowResultRecordDecodeError,
        match="non-finite",
    ):
        replay_shadow_result_record_v1(
            tampered
        )


def test_unknown_top_level_key_is_rejected():
    record = _record_dict()

    record[
        "unexpected"
    ] = True

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


@pytest.mark.parametrize(
    "missing_key",
    tuple(
        sorted(
            TOP_LEVEL_KEYS
        )
    ),
)
def test_missing_top_level_key_is_rejected(
    missing_key,
):
    record = _record_dict()

    del record[
        missing_key
    ]

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_wrong_record_schema_is_rejected():
    record = _record_dict()

    record[
        "record_schema_version"
    ] = "WRONG_RECORD_SCHEMA"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_wrong_result_schema_header_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_schema_version"
    ] = "WRONG_RESULT_SCHEMA"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_invalid_declared_result_hash_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_sha256"
    ] = "not-a-hash"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_invalid_top_snapshot_hash_is_rejected():
    record = _record_dict()

    record[
        "snapshot_sha256"
    ] = "bad"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_top_snapshot_payload_mismatch_is_rejected():
    record = _record_dict()

    record[
        "snapshot_sha256"
    ] = (
        "0"
        * 64
    )

    assert (
        record[
            "snapshot_sha256"
        ]
        != record[
            "shadow_result_payload"
        ][
            "snapshot_sha256"
        ]
    )

    with pytest.raises(
        ShadowResultIntegrityError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_payload_change_with_stale_result_hash_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "source_runtime_ref"
    ] = "STEP6C_RUNTIME_TAMPERED"

    with pytest.raises(
        ShadowResultIntegrityError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_declared_result_hash_tamper_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_sha256"
    ] = (
        "0"
        * 64
    )

    with pytest.raises(
        ShadowResultIntegrityError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_unknown_result_payload_key_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "unexpected"
    ] = "x"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


@pytest.mark.parametrize(
    "missing_key",
    (
        "market",
        "snapshot_sha256",
        "hypothesis",
    ),
)
def test_missing_critical_result_payload_key_is_rejected(
    missing_key,
):
    record = _record_dict()

    del record[
        "shadow_result_payload"
    ][
        missing_key
    ]

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_wrong_payload_result_schema_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "schema_version"
    ] = "WRONG_PAYLOAD_SCHEMA"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_wrong_hypothesis_schema_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "hypothesis"
    ][
        "schema_version"
    ] = "WRONG_HYPOTHESIS_SCHEMA"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_unknown_hypothesis_key_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "hypothesis"
    ][
        "unexpected"
    ] = True

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


@pytest.mark.parametrize(
    "missing_key",
    (
        "market",
        "hypothesis",
        "rationale_codes",
    ),
)
def test_missing_critical_hypothesis_key_is_rejected(
    missing_key,
):
    record = _record_dict()

    del record[
        "shadow_result_payload"
    ][
        "hypothesis"
    ][
        missing_key
    ]

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


@pytest.mark.parametrize(
    "authority_field",
    (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ),
)
def test_replay_rejects_true_authority_payload(
    authority_field,
):
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        authority_field
    ] = True

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_invalid_snapshot_datetime_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "snapshot_at"
    ] = "not-a-datetime"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_naive_snapshot_datetime_is_rejected():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "snapshot_at"
    ] = "2026-09-30T12:00:00"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_tuple_field_must_decode_from_json_array():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "missing_production_analyzers"
    ] = "not-an-array"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_tuple_members_must_be_strings():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "stale_evidence_ids"
    ] = [
        123
    ]

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_hypothesis_market_must_match_result_market():
    record = _record_dict()

    record[
        "shadow_result_payload"
    ][
        "hypothesis"
    ][
        "market"
    ] = "SENSEX"

    with pytest.raises(
        ShadowResultSchemaError
    ):
        replay_shadow_result_record_v1(
            _json(
                record
            )
        )


def test_load_non_utf8_is_rejected(
    tmp_path,
):
    path = (
        tmp_path
        / "bad.json"
    )

    path.write_bytes(
        b"\xff\xfe\xff"
    )

    with pytest.raises(
        ShadowResultRecordDecodeError
    ):
        load_shadow_result_record_v1(
            path
        )


def test_load_missing_file_is_persistence_error(
    tmp_path,
):
    path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(
        ShadowResultPersistenceError
    ):
        load_shadow_result_record_v1(
            path
        )


def test_canonical_replay_equality_is_exact():
    result = _result(
        "NATGASMINI"
    )

    replayed = (
        replay_shadow_result_record_v1(
            serialize_shadow_result_record_v1(
                result
            )
        )
    )

    assert (
        replayed.canonical_json()
        == result.canonical_json()
    )

    assert (
        replayed.shadow_result_sha256
        == result.shadow_result_sha256
    )


def test_module_has_no_provider_broker_or_runtime_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_persistence_v1.py"
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
        "snapshot_journal_v1",
        "snapshot_persistence_v1",
        "shadow_composer_v1",
        "shadow_result_journal_v1",
    )

    assert not any(
        token in module
        for module
        in imports
        for token
        in forbidden
    )


def test_module_has_no_clock_random_trade_or_pnl_surface():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_persistence_v1.py"
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
    )

    assert not any(
        token in source
        for token
        in forbidden
    )


def test_module_contains_immutable_atomic_publication_primitives():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_result_persistence_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    assert "os.fsync(" in source
    assert "os.link(" in source
    assert "NamedTemporaryFile" in source
