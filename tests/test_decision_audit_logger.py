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


# ===================================
# TESTS FOR get_recent_records()
# ===================================


def test_get_recent_records_returns_last_n(
    tmp_path,
):
    """Verify get_recent_records returns the last N records in order."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    # Log 5 records
    for i in range(1, 6):
        logger.log(
            audit_trail=make_audit_trail(
                f"DECISION_{i}"
            )
        )

    # Get last 3
    recent = logger.get_recent_records(limit=3)

    assert len(recent) == 3

    assert (
        recent[0]["final_decision"]
        == "DECISION_3"
    )

    assert (
        recent[1]["final_decision"]
        == "DECISION_4"
    )

    assert (
        recent[2]["final_decision"]
        == "DECISION_5"
    )


def test_get_recent_records_default_limit(
    tmp_path,
):
    """Verify default limit is 10."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    # Log 15 records
    for i in range(1, 16):
        logger.log(
            audit_trail=make_audit_trail(
                f"DECISION_{i}"
            )
        )

    # Get recent with default limit
    recent = logger.get_recent_records()

    assert len(recent) == 10

    assert (
        recent[0]["final_decision"]
        == "DECISION_6"
    )

    assert (
        recent[9]["final_decision"]
        == "DECISION_15"
    )


def test_get_recent_records_limit_one(
    tmp_path,
):
    """Verify limit=1 returns single most recent record."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail("FIRST")
    )

    logger.log(
        audit_trail=make_audit_trail("SECOND")
    )

    logger.log(
        audit_trail=make_audit_trail("THIRD")
    )

    recent = logger.get_recent_records(limit=1)

    assert len(recent) == 1

    assert (
        recent[0]["final_decision"]
        == "THIRD"
    )


def test_get_recent_records_limit_exceeds_count(
    tmp_path,
):
    """Verify limit > record count returns all records."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail("ONE")
    )

    logger.log(
        audit_trail=make_audit_trail("TWO")
    )

    logger.log(
        audit_trail=make_audit_trail("THREE")
    )

    recent = logger.get_recent_records(limit=100)

    assert len(recent) == 3

    assert (
        recent[0]["final_decision"]
        == "ONE"
    )

    assert (
        recent[2]["final_decision"]
        == "THREE"
    )


def test_get_recent_records_missing_file(
    tmp_path,
):
    """Verify missing file returns empty list."""

    logger = DecisionAuditLogger(
        file_path=(
            tmp_path
            / "nonexistent"
            / "decisions.jsonl"
        )
    )

    recent = logger.get_recent_records(limit=10)

    assert recent == []


def test_get_recent_records_empty_file(
    tmp_path,
):
    """Verify empty file returns empty list."""

    file_path = tmp_path / "empty.jsonl"

    file_path.write_text("", encoding="utf-8")

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    recent = logger.get_recent_records(limit=10)

    assert recent == []


def test_get_recent_records_limit_zero_rejected():
    """Verify limit=0 raises ValueError."""

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be >= 1",
    ):
        logger.get_recent_records(limit=0)


def test_get_recent_records_limit_negative_rejected():
    """Verify negative limit raises ValueError."""

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be >= 1",
    ):
        logger.get_recent_records(limit=-5)


def test_get_recent_records_limit_float_rejected():
    """Verify float limit raises ValueError."""

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be an integer",
    ):
        logger.get_recent_records(limit=3.14)


def test_get_recent_records_limit_string_rejected():
    """Verify string limit raises ValueError."""

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be an integer",
    ):
        logger.get_recent_records(limit="10")


def test_get_recent_records_limit_boolean_rejected():
    """Verify boolean limit raises ValueError (even though bool is subclass of int)."""

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be an integer, not a boolean",
    ):
        logger.get_recent_records(limit=True)

    with pytest.raises(
        ValueError,
        match="Limit must be an integer, not a boolean",
    ):
        logger.get_recent_records(limit=False)


def test_get_recent_records_returns_copies(
    tmp_path,
):
    """Verify returned records are deep copies and cannot mutate persisted data."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    logger.log(
        audit_trail=make_audit_trail("ORIGINAL"),
        metadata={
            "underlying": "NIFTY",
            "spot_price": 24206,
        },
    )

    recent = logger.get_recent_records(limit=1)

    # Mutate the returned record
    recent[0]["final_decision"] = "MUTATED"

    recent[0]["metadata"]["underlying"] = "MUTATED"

    recent[0]["audit_trail"]["events"][0][
        "stage"
    ] = "MUTATED"

    # Verify the persisted record is unchanged
    again = logger.get_recent_records(limit=1)

    assert (
        again[0]["final_decision"]
        == "ORIGINAL"
    )

    assert (
        again[0]["metadata"]["underlying"]
        == "NIFTY"
    )

    assert (
        again[0]["audit_trail"]["events"][0][
            "stage"
        ]
        == "MARKET_ANALYSIS"
    )


def test_get_recent_records_fail_closed_on_invalid_json(
    tmp_path,
):
    """Verify malformed records cause ValueError (fail-closed behavior)."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    # Write a valid record
    logger.log(
        audit_trail=make_audit_trail("VALID")
    )

    # Write an invalid JSON record
    with file_path.open(
        mode="a",
        encoding="utf-8",
    ) as f:
        f.write("not-valid-json\n")

    # Attempting to get recent records should raise ValueError
    with pytest.raises(
        ValueError,
        match="Invalid JSON audit record",
    ):
        logger.get_recent_records(limit=10)


def test_get_recent_records_chronological_order(
    tmp_path,
):
    """Verify records are returned in chronological order (oldest to newest)."""

    file_path = tmp_path / "decisions.jsonl"

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    # Log records with specific decisions
    decisions = [
        "MORNING_DECISION",
        "MIDDAY_DECISION",
        "AFTERNOON_DECISION",
        "EVENING_DECISION",
    ]

    for decision in decisions:
        logger.log(
            audit_trail=make_audit_trail(
                decision
            )
        )

    recent = logger.get_recent_records(limit=10)

    assert len(recent) == 4

    for i, decision in enumerate(decisions):
        assert (
            recent[i]["final_decision"]
            == decision
        )