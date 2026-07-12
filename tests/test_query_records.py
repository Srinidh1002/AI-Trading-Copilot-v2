"""
Integration tests for query_records and get_summary_statistics.
"""

import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from services.decision_audit_logger import (
    DecisionAuditLogger,
)


def make_record(
    logged_at,
    final_decision,
    underlying,
    spot_price=None,
    event_count=5,
):
    """
    Helper to create a complete audit record.
    """

    return {
        "logged_at": logged_at,
        "final_decision": final_decision,
        "event_count": event_count,
        "metadata": {
            "exchange": "NSE",
            "symboltoken": "99926000",
            "underlying": underlying,
            "spot_price": (
                spot_price
                if spot_price is not None
                else 24206.50
            ),
            "final_decision": final_decision,
        },
        "audit_trail": {
            "events": [
                {
                    "sequence": i,
                    "stage": "STAGE",
                    "status": "COMPLETED",
                    "decision": final_decision,
                    "reasons": [],
                    "details": {},
                }
                for i in range(event_count)
            ],
            "final_decision": final_decision,
            "event_count": event_count,
        },
    }


def test_query_records_empty_file(
    tmp_path,
):
    """
    Empty or missing file returns empty list.
    """

    logger = DecisionAuditLogger(
        file_path=(
            tmp_path / "missing.jsonl"
        )
    )

    result = logger.query_records()

    assert result == []


def test_query_records_all_records(
    tmp_path,
):
    """
    Query with no filters returns all records.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    # Write test records
    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "BANKNIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records()

    assert len(result) == 3

    # Verify chronological order
    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:00:00+00:00"
    )

    assert (
        result[2]["logged_at"]
        == "2026-07-12T10:10:00+00:00"
    )


def test_query_records_by_decision(
    tmp_path,
):
    """
    Filter records by final_decision.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        final_decision="TRADE_ALLOWED"
    )

    assert len(result) == 1

    assert (
        result[0]["final_decision"]
        == "TRADE_ALLOWED"
    )

    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:05:00+00:00"
    )


def test_query_records_by_underlying(
    tmp_path,
):
    """
    Filter records by underlying asset.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        underlying="NIFTY"
    )

    assert len(result) == 2

    assert (
        result[0]["metadata"]["underlying"]
        == "NIFTY"
    )

    assert (
        result[1]["metadata"]["underlying"]
        == "NIFTY"
    )


def test_query_records_by_start_time(
    tmp_path,
):
    """
    Filter records by start time (inclusive).
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        start_time="2026-07-12T10:05:00+00:00"
    )

    assert len(result) == 2

    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:05:00+00:00"
    )

    assert (
        result[1]["logged_at"]
        == "2026-07-12T10:10:00+00:00"
    )


def test_query_records_by_end_time(
    tmp_path,
):
    """
    Filter records by end time (inclusive).
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        end_time="2026-07-12T10:05:00+00:00"
    )

    assert len(result) == 2

    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:00:00+00:00"
    )

    assert (
        result[1]["logged_at"]
        == "2026-07-12T10:05:00+00:00"
    )


def test_query_records_by_time_range(
    tmp_path,
):
    """
    Filter by both start and end time.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:15:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        start_time="2026-07-12T10:05:00+00:00",
        end_time="2026-07-12T10:10:00+00:00",
    )

    assert len(result) == 2

    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:05:00+00:00"
    )

    assert (
        result[1]["logged_at"]
        == "2026-07-12T10:10:00+00:00"
    )


def test_query_records_combined_filters(
    tmp_path,
):
    """
    Filter by decision, underlying, and time range.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
        make_record(
            "2026-07-12T10:15:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        final_decision="TRADE_ALLOWED",
        underlying="NIFTY",
        start_time="2026-07-12T10:05:00+00:00",
    )

    assert len(result) == 2

    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:05:00+00:00"
    )

    assert (
        result[1]["logged_at"]
        == "2026-07-12T10:15:00+00:00"
    )


def test_query_records_with_limit(
    tmp_path,
):
    """
    Apply limit to filtered results.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            f"2026-07-12T10:{i:02d}:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        )
        for i in range(10)
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    result = logger.query_records(
        limit=3
    )

    assert len(result) == 3

    # Should return last 3 in order
    assert (
        result[0]["logged_at"]
        == "2026-07-12T10:07:00+00:00"
    )

    assert (
        result[2]["logged_at"]
        == "2026-07-12T10:09:00+00:00"
    )


def test_query_records_invalid_limit_zero():
    """
    Limit of 0 raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be >= 1",
    ):
        logger.query_records(
            limit=0
        )


def test_query_records_invalid_limit_negative():
    """
    Negative limit raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be >= 1",
    ):
        logger.query_records(
            limit=-5
        )


def test_query_records_invalid_limit_boolean():
    """
    Boolean limit raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be an integer",
    ):
        logger.query_records(
            limit=True
        )


def test_query_records_invalid_limit_type():
    """
    Invalid type for limit raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Limit must be an integer",
    ):
        logger.query_records(
            limit="10"
        )


def test_query_records_invalid_start_time():
    """
    Invalid start_time raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Invalid timestamp format",
    ):
        logger.query_records(
            start_time="not-a-timestamp"
        )


def test_query_records_invalid_end_time():
    """
    Invalid end_time raises ValueError.
    """

    logger = DecisionAuditLogger(
        file_path="unused.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="Invalid timestamp format",
    ):
        logger.query_records(
            end_time="not-a-timestamp"
        )


def test_query_records_immutable_results(
    tmp_path,
):
    """
    Returned records are deep copies.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    record = make_record(
        "2026-07-12T10:00:00+00:00",
        "NO_TRADE",
        "NIFTY",
    )

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(record) + "\n"
        )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    results = logger.query_records()

    # Mutate the result
    results[0]["metadata"]["underlying"] = (
        "MODIFIED"
    )

    # Re-read and verify original unchanged
    results2 = logger.query_records()

    assert (
        results2[0]["metadata"]["underlying"]
        == "NIFTY"
    )


def test_get_summary_statistics_empty(
    tmp_path,
):
    """
    Empty log returns empty statistics.
    """

    logger = DecisionAuditLogger(
        file_path=(
            tmp_path / "missing.jsonl"
        )
    )

    stats = logger.get_summary_statistics()

    assert stats["total_records"] == 0

    assert stats["count_by_decision"] == {}

    assert stats["count_by_underlying"] == {}

    assert stats["earliest_logged_at"] is None

    assert stats["latest_logged_at"] is None


def test_get_summary_statistics_all_records(
    tmp_path,
):
    """
    Statistics for all records.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "BANKNIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    stats = logger.get_summary_statistics()

    assert stats["total_records"] == 3

    assert stats["count_by_decision"]["NO_TRADE"] == 2

    assert (
        stats["count_by_decision"][
            "TRADE_ALLOWED"
        ]
        == 1
    )

    assert stats["count_by_underlying"]["NIFTY"] == 2

    assert (
        stats["count_by_underlying"][
            "BANKNIFTY"
        ]
        == 1
    )

    assert (
        stats["earliest_logged_at"]
        == "2026-07-12T10:00:00+00:00"
    )

    assert (
        stats["latest_logged_at"]
        == "2026-07-12T10:10:00+00:00"
    )


def test_get_summary_statistics_with_filters(
    tmp_path,
):
    """
    Statistics with filters applied.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    stats = logger.get_summary_statistics(
        underlying="NIFTY"
    )

    assert stats["total_records"] == 2

    assert stats["count_by_decision"]["NO_TRADE"] == 1

    assert (
        stats["count_by_decision"][
            "TRADE_ALLOWED"
        ]
        == 1
    )

    assert stats["count_by_underlying"]["NIFTY"] == 2

    assert (
        "BANKNIFTY"
        not in stats["count_by_underlying"]
    )


def test_get_summary_statistics_with_limit(
    tmp_path,
):
    """
    Statistics counts all records matching filters,
    limit parameter is ignored for statistics.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            f"2026-07-12T10:{i:02d}:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        )
        for i in range(10)
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    logger = DecisionAuditLogger(
        file_path=file_path
    )

    stats = logger.get_summary_statistics(
        limit=5
    )

    # Statistics counts all matching records,
    # even if limit is specified (limit is ignored)
    assert stats["total_records"] == 10

    assert stats["count_by_decision"]["TRADE_ALLOWED"] == 10
