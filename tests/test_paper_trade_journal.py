"""
Tests for persistent paper-trade lifecycle journaling.
"""

import json

import pytest

from services.paper_trade_journal import (
    PaperTradeJournal,
)


def make_event(
    trade_id="paper-001",
    event="OPENED",
    sequence=1,
    status="OPEN",
):
    return {
        "sequence": sequence,
        "timestamp": (
            "2026-07-12T10:00:00+00:00"
        ),
        "trade_id": trade_id,
        "event": event,
        "status": status,
        "price": 100.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "reason": None,
        "details": {
            "source": "test"
        },
    }


def make_journal(
    tmp_path,
):
    return PaperTradeJournal(
        file_path=(
            tmp_path
            / "paper_trade_journal.jsonl"
        ),
        timestamp_factory=(
            lambda: (
                "2026-07-12T10:01:00+00:00"
            )
        ),
    )


def test_default_path():
    journal = (
        PaperTradeJournal()
    )

    assert (
        str(
            journal.file_path
        )
        .replace(
            "\\",
            "/",
        )
        .endswith(
            "data/paper_trading/"
            "paper_trade_journal.jsonl"
        )
    )


def test_build_record():
    journal = (
        PaperTradeJournal(
            timestamp_factory=(
                lambda: "logged-time"
            )
        )
    )

    record = journal.build_record(
        lifecycle_event=(
            make_event()
        )
    )

    assert (
        record["logged_at"]
        == "logged-time"
    )

    assert (
        record["trade_id"]
        == "paper-001"
    )

    assert (
        record["event"]
        == "OPENED"
    )


def test_log_creates_file(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event()
    )

    assert (
        journal.file_path.exists()
    )


def test_log_writes_valid_json(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event()
    )

    line = (
        journal.file_path
        .read_text(
            encoding="utf-8"
        )
        .strip()
    )

    record = json.loads(
        line
    )

    assert (
        record["trade_id"]
        == "paper-001"
    )


def test_log_is_append_only(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event(
            event="OPENED",
            sequence=1,
        )
    )

    journal.log(
        make_event(
            event="PRICE_UPDATED",
            sequence=2,
        )
    )

    lines = (
        journal.file_path
        .read_text(
            encoding="utf-8"
        )
        .strip()
        .splitlines()
    )

    assert (
        len(
            lines
        )
        == 2
    )


def test_read_missing_file_returns_empty(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    assert (
        journal.read_records()
        == []
    )


def test_read_records(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event(
            event="OPENED",
            sequence=1,
        )
    )

    journal.log(
        make_event(
            event="PRICE_UPDATED",
            sequence=2,
        )
    )

    records = (
        journal.read_records()
    )

    assert (
        len(
            records
        )
        == 2
    )

    assert (
        records[
            0
        ][
            "event"
        ]
        == "OPENED"
    )

    assert (
        records[
            1
        ][
            "event"
        ]
        == "PRICE_UPDATED"
    )


def test_metadata_is_preserved(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event(),
        metadata={
            "underlying": "NIFTY"
        },
    )

    record = (
        journal.read_records()[
            0
        ]
    )

    assert (
        record[
            "metadata"
        ][
            "underlying"
        ]
        == "NIFTY"
    )


def test_metadata_is_defensively_copied(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    metadata = {
        "nested": {
            "value": 1
        }
    }

    record = journal.build_record(
        lifecycle_event=(
            make_event()
        ),
        metadata=metadata,
    )

    metadata[
        "nested"
    ][
        "value"
    ] = 999

    assert (
        record[
            "metadata"
        ][
            "nested"
        ][
            "value"
        ]
        == 1
    )


def test_lifecycle_event_is_defensively_copied():
    journal = (
        PaperTradeJournal()
    )

    event = make_event()

    record = journal.build_record(
        lifecycle_event=event
    )

    event[
        "details"
    ][
        "source"
    ] = "changed"

    assert (
        record[
            "lifecycle_event"
        ][
            "details"
        ][
            "source"
        ]
        == "test"
    )


@pytest.mark.parametrize(
    "invalid_event",
    [
        None,
        [],
        "invalid",
        123,
    ],
)
def test_invalid_lifecycle_event_type_rejected(
    invalid_event,
):
    journal = (
        PaperTradeJournal()
    )

    with pytest.raises(
        TypeError
    ):
        journal.build_record(
            lifecycle_event=(
                invalid_event
            )
        )


@pytest.mark.parametrize(
    "trade_id",
    [
        None,
        "",
        "   ",
        123,
        True,
    ],
)
def test_invalid_trade_id_rejected(
    trade_id,
):
    journal = (
        PaperTradeJournal()
    )

    event = make_event(
        trade_id=trade_id
    )

    with pytest.raises(
        ValueError
    ):
        journal.build_record(
            lifecycle_event=event
        )


@pytest.mark.parametrize(
    "sequence",
    [
        None,
        0,
        -1,
        1.5,
        "1",
        True,
    ],
)
def test_invalid_sequence_rejected(
    sequence,
):
    journal = (
        PaperTradeJournal()
    )

    event = make_event(
        sequence=sequence
    )

    with pytest.raises(
        ValueError
    ):
        journal.build_record(
            lifecycle_event=event
        )


def test_invalid_metadata_rejected():
    journal = (
        PaperTradeJournal()
    )

    with pytest.raises(
        TypeError
    ):
        journal.build_record(
            lifecycle_event=(
                make_event()
            ),
            metadata=[
                "invalid"
            ],
        )


def test_invalid_json_fails_closed(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.file_path.write_text(
        "{invalid json}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="line 1",
    ):
        journal.read_records()


def test_non_dictionary_json_fails_closed(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.file_path.write_text(
        '["invalid"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        journal.read_records()


def test_trade_id_mismatch_fails_closed(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    record = journal.build_record(
        make_event()
    )

    record[
        "trade_id"
    ] = "different"

    journal.file_path.write_text(
        json.dumps(
            record
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        journal.read_records()


def test_event_mismatch_fails_closed(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    record = journal.build_record(
        make_event()
    )

    record[
        "event"
    ] = "CLOSED"

    journal.file_path.write_text(
        json.dumps(
            record
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        journal.read_records()


def test_get_recent_records(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    for sequence in range(
        1,
        6,
    ):
        journal.log(
            make_event(
                trade_id=(
                    f"paper-{sequence}"
                ),
                sequence=sequence,
            )
        )

    records = (
        journal.get_recent_records(
            limit=2
        )
    )

    assert [
        record["trade_id"]
        for record in records
    ] == [
        "paper-4",
        "paper-5",
    ]


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        1.5,
        "1",
        True,
        None,
    ],
)
def test_invalid_recent_limit_rejected(
    limit,
):
    journal = (
        PaperTradeJournal()
    )

    with pytest.raises(
        ValueError
    ):
        journal.get_recent_records(
            limit=limit
        )


def test_get_records_for_trade(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event(
            trade_id="paper-001",
            sequence=1,
        )
    )

    journal.log(
        make_event(
            trade_id="paper-002",
            sequence=1,
        )
    )

    journal.log(
        make_event(
            trade_id="paper-001",
            event="CLOSED",
            sequence=2,
            status="CLOSED",
        )
    )

    records = (
        journal.get_records_for_trade(
            "paper-001"
        )
    )

    assert (
        len(
            records
        )
        == 2
    )

    assert all(
        record[
            "trade_id"
        ]
        == "paper-001"
        for record in records
    )


def test_get_records_by_event(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event(
            event="OPENED",
            sequence=1,
        )
    )

    journal.log(
        make_event(
            event="PRICE_UPDATED",
            sequence=2,
        )
    )

    journal.log(
        make_event(
            event="CLOSED",
            sequence=3,
            status="CLOSED",
        )
    )

    records = (
        journal.get_records_by_event(
            "closed"
        )
    )

    assert (
        len(
            records
        )
        == 1
    )

    assert (
        records[
            0
        ][
            "event"
        ]
        == "CLOSED"
    )


def test_count_records(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    assert (
        journal.count_records()
        == 0
    )

    journal.log(
        make_event(
            sequence=1
        )
    )

    journal.log(
        make_event(
            sequence=2
        )
    )

    assert (
        journal.count_records()
        == 2
    )


def test_read_records_returns_defensive_copy(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event()
    )

    records = (
        journal.read_records()
    )

    records[
        0
    ][
        "trade_id"
    ] = "changed"

    reread = (
        journal.read_records()
    )

    assert (
        reread[
            0
        ][
            "trade_id"
        ]
        == "paper-001"
    )


def test_empty_lines_are_ignored(
    tmp_path,
):
    journal = make_journal(
        tmp_path
    )

    journal.log(
        make_event()
    )

    with journal.file_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            "\n\n"
        )

    assert (
        journal.count_records()
        == 1
    )


def test_parent_directories_created(
    tmp_path,
):
    file_path = (
        tmp_path
        / "nested"
        / "paper"
        / "journal.jsonl"
    )

    journal = (
        PaperTradeJournal(
            file_path=file_path
        )
    )

    journal.log(
        make_event()
    )

    assert (
        file_path.exists()
    )