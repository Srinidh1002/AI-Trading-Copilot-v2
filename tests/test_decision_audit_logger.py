"""
Tests for the persistent decision audit logger.
"""

import json

import pytest

from services.decision_audit_logger import (
    DecisionAuditLogger,
)


def make_audit_trail(
    final_decision="NO_TRADE",
):
    return {
        "final_decision": final_decision,
        "event_count": 2,
        "events": [
            {
                "sequence": 1,
                "stage": "MARKET_ANALYSIS",
                "status": "COMPLETED",
                "decision": "NO_TRADE",
                "reasons": [],
                "details": {},
            },
            {
                "sequence": 2,
                "stage": "FINAL_DECISION",
                "status": "COMPLETED",
                "decision": final_decision,
                "reasons": [],
                "details": {},
            },
        ],
    }


def test_build_record():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl",
        timestamp_factory=lambda: (
            "2026-07-12T10:00:00+00:00"
        ),
    )

    record = logger.build_record(
        audit_trail=make_audit_trail(),
        metadata={
            "underlying": "NIFTY",
            "spot_price": 24206,
        },
    )

    assert (
        record["logged_at"]
        == "2026-07-12T10:00:00+00:00"
    )

    assert (
        record["final_decision"]
        == "NO_TRADE"
    )

    assert record["event_count"] == 2

    assert (
        record["metadata"]["underlying"]
        == "NIFTY"
    )


def test_log_creates_file(
    tmp_path,
):

    file_path = (
        tmp_path
        / "audit"
        / "decisions.jsonl"
    )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail()
    )

    assert file_path.exists()


def test_log_writes_valid_json_line(
    tmp_path,
):

    file_path = (
        tmp_path
        / "decisions.jsonl"
    )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail(),
        metadata={
            "underlying": "NIFTY",
        },
    )

    lines = file_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 1

    record = json.loads(
        lines[0]
    )

    assert (
        record["final_decision"]
        == "NO_TRADE"
    )

    assert (
        record["metadata"]["underlying"]
        == "NIFTY"
    )


def test_log_is_append_only(
    tmp_path,
):

    file_path = (
        tmp_path
        / "decisions.jsonl"
    )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail(
            "NO_TRADE"
        )
    )

    logger.log(
        audit_trail=make_audit_trail(
            "TRADE_ALLOWED"
        )
    )

    records = logger.read_records()

    assert len(records) == 2

    assert (
        records[0]["final_decision"]
        == "NO_TRADE"
    )

    assert (
        records[1]["final_decision"]
        == "TRADE_ALLOWED"
    )


def test_read_missing_file_returns_empty_list(
    tmp_path,
):

    logger = DecisionAuditLogger(
        file_path=(
            tmp_path
            / "missing.jsonl"
        )
    )

    assert logger.read_records() == []


def test_invalid_audit_type_rejected():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        TypeError,
        match="Audit trail must be a dictionary",
    ):
        logger.build_record(
            audit_trail=[]
        )


def test_missing_events_rejected():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="events list",
    ):
        logger.build_record(
            audit_trail={
                "event_count": 0,
            }
        )


def test_event_count_mismatch_rejected():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    audit = make_audit_trail()

    audit["event_count"] = 99

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        logger.build_record(
            audit_trail=audit
        )


def test_invalid_metadata_rejected():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        TypeError,
        match="metadata must be",
    ):
        logger.build_record(
            audit_trail=make_audit_trail(),
            metadata=[],
        )


def test_read_invalid_json_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "decisions.jsonl"
    )

    file_path.write_text(
        "not-valid-json\n",
        encoding="utf-8",
    )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    with pytest.raises(
        ValueError,
        match="Invalid JSON audit record",
    ):
        logger.read_records()


def test_input_data_is_not_mutated():

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    audit = make_audit_trail()

    metadata = {
        "underlying": "NIFTY",
    }

    record = logger.build_record(
        audit_trail=audit,
        metadata=metadata,
    )

    record[
        "audit_trail"
    ][
        "events"
    ][0][
        "stage"
    ] = "CHANGED"

    record[
        "metadata"
    ][
        "underlying"
    ] = "CHANGED"

    assert (
        audit["events"][0]["stage"]
        == "MARKET_ANALYSIS"
    )

    assert (
        metadata["underlying"]
        == "NIFTY"
    )