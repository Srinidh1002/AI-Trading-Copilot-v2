"""
Tests for paper-trade lifecycle auditing.
"""

from copy import deepcopy

import pytest

from services.paper_trade_lifecycle_audit import (
    PaperTradeLifecycleAudit,
    PaperTradeLifecycleEvent,
)


def make_audit():
    return PaperTradeLifecycleAudit(
        trade_id="paper-001",
        timestamp_factory=(
            lambda: (
                "2026-07-12T10:00:00+00:00"
            )
        ),
    )


def test_create_audit():
    audit = make_audit()

    assert (
        audit.trade_id
        == "paper-001"
    )

    assert (
        audit.count_events()
        == 0
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
    with pytest.raises(
        ValueError
    ):
        PaperTradeLifecycleAudit(
            trade_id=trade_id
        )


def test_non_callable_timestamp_factory_rejected():
    with pytest.raises(
        TypeError
    ):
        PaperTradeLifecycleAudit(
            trade_id="paper-001",
            timestamp_factory="invalid",
        )


def test_record_opened():
    audit = make_audit()

    event = audit.record_opened(
        price=100,
    )

    assert (
        event["event"]
        == PaperTradeLifecycleEvent.OPENED
    )

    assert (
        event["status"]
        == "OPEN"
    )

    assert (
        event["price"]
        == 100.0
    )


def test_record_price_updated():
    audit = make_audit()

    event = (
        audit.record_price_updated(
            price=110,
            unrealized_pnl=750,
        )
    )

    assert (
        event["event"]
        == (
            PaperTradeLifecycleEvent
            .PRICE_UPDATED
        )
    )

    assert (
        event["unrealized_pnl"]
        == 750.0
    )


def test_record_stop_loss_hit():
    audit = make_audit()

    event = (
        audit.record_stop_loss_hit(
            price=80,
            realized_pnl=-1500,
        )
    )

    assert (
        event["event"]
        == (
            PaperTradeLifecycleEvent
            .STOP_LOSS_HIT
        )
    )

    assert (
        event["status"]
        == "CLOSED"
    )


def test_record_target_hit():
    audit = make_audit()

    event = (
        audit.record_target_hit(
            price=140,
            realized_pnl=3000,
        )
    )

    assert (
        event["event"]
        == (
            PaperTradeLifecycleEvent
            .TARGET_HIT
        )
    )


def test_record_closed():
    audit = make_audit()

    event = audit.record_closed(
        price=110,
        realized_pnl=750,
        reason="Manual paper exit.",
    )

    assert (
        event["event"]
        == PaperTradeLifecycleEvent.CLOSED
    )

    assert (
        event["realized_pnl"]
        == 750.0
    )


def test_sequence_numbers_are_sequential():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    audit.record_price_updated(
        price=110,
        unrealized_pnl=750,
    )

    audit.record_closed(
        price=110,
        realized_pnl=750,
    )

    events = (
        audit.get_events()
    )

    assert [
        event["sequence"]
        for event in events
    ] == [
        1,
        2,
        3,
    ]


def test_timestamp_factory_used():
    audit = make_audit()

    event = audit.record_opened(
        price=100
    )

    assert (
        event["timestamp"]
        == (
            "2026-07-12T10:00:00+00:00"
        )
    )


def test_explicit_timestamp_used():
    audit = make_audit()

    event = audit.record_opened(
        price=100,
        timestamp=(
            "2026-07-12T11:00:00+00:00"
        ),
    )

    assert (
        event["timestamp"]
        == (
            "2026-07-12T11:00:00+00:00"
        )
    )


@pytest.mark.parametrize(
    "invalid_event",
    [
        None,
        "",
        "INVALID",
        123,
    ],
)
def test_invalid_event_rejected(
    invalid_event,
):
    audit = make_audit()

    with pytest.raises(
        ValueError
    ):
        audit.record(
            event=invalid_event,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        0,
        -1,
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
    ],
)
def test_invalid_price_rejected(
    invalid_price,
):
    audit = make_audit()

    with pytest.raises(
        ValueError
    ):
        audit.record_opened(
            price=invalid_price
        )


@pytest.mark.parametrize(
    "invalid_pnl",
    [
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
    ],
)
def test_invalid_pnl_rejected(
    invalid_pnl,
):
    audit = make_audit()

    with pytest.raises(
        ValueError
    ):
        audit.record_price_updated(
            price=100,
            unrealized_pnl=(
                invalid_pnl
            ),
        )


def test_negative_pnl_is_allowed():
    audit = make_audit()

    event = (
        audit.record_price_updated(
            price=90,
            unrealized_pnl=-750,
        )
    )

    assert (
        event["unrealized_pnl"]
        == -750.0
    )


def test_zero_pnl_is_allowed():
    audit = make_audit()

    event = (
        audit.record_price_updated(
            price=100,
            unrealized_pnl=0,
        )
    )

    assert (
        event["unrealized_pnl"]
        == 0.0
    )


def test_details_must_be_dictionary():
    audit = make_audit()

    with pytest.raises(
        TypeError
    ):
        audit.record_opened(
            price=100,
            details=[
                "invalid"
            ],
        )


def test_details_are_defensively_copied():
    audit = make_audit()

    details = {
        "nested": {
            "value": 1
        }
    }

    event = audit.record_opened(
        price=100,
        details=details,
    )

    details[
        "nested"
    ][
        "value"
    ] = 999

    assert (
        event[
            "details"
        ][
            "nested"
        ][
            "value"
        ]
        == 1
    )


def test_returned_event_cannot_mutate_history():
    audit = make_audit()

    event = audit.record_opened(
        price=100,
        details={
            "value": 1
        },
    )

    event[
        "price"
    ] = 999

    event[
        "details"
    ][
        "value"
    ] = 999

    stored = (
        audit.latest_event()
    )

    assert (
        stored["price"]
        == 100.0
    )

    assert (
        stored[
            "details"
        ][
            "value"
        ]
        == 1
    )


def test_get_events_returns_defensive_copy():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    events = (
        audit.get_events()
    )

    events[
        0
    ][
        "price"
    ] = 999

    stored = (
        audit.get_events()
    )

    assert (
        stored[
            0
        ][
            "price"
        ]
        == 100.0
    )


def test_latest_event_empty_returns_none():
    audit = make_audit()

    assert (
        audit.latest_event()
        is None
    )


def test_latest_event_returns_last_event():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    audit.record_price_updated(
        price=110,
        unrealized_pnl=750,
    )

    latest = (
        audit.latest_event()
    )

    assert (
        latest["event"]
        == (
            PaperTradeLifecycleEvent
            .PRICE_UPDATED
        )
    )


def test_build_summary_empty():
    audit = make_audit()

    summary = (
        audit.build_summary()
    )

    assert summary == {
        "trade_id": "paper-001",
        "event_count": 0,
        "latest_event": None,
        "latest_status": None,
        "events": [],
    }


def test_build_summary_complete():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    audit.record_closed(
        price=110,
        realized_pnl=750,
    )

    summary = (
        audit.build_summary()
    )

    assert (
        summary["trade_id"]
        == "paper-001"
    )

    assert (
        summary["event_count"]
        == 2
    )

    assert (
        summary["latest_event"]
        == "CLOSED"
    )

    assert (
        summary["latest_status"]
        == "CLOSED"
    )


def test_summary_is_defensive_copy():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    summary = (
        audit.build_summary()
    )

    original = deepcopy(
        summary
    )

    summary[
        "events"
    ][
        0
    ][
        "price"
    ] = 999

    rebuilt = (
        audit.build_summary()
    )

    assert (
        rebuilt
        == original
    )


def test_clear_removes_events():
    audit = make_audit()

    audit.record_opened(
        price=100
    )

    audit.clear()

    assert (
        audit.count_events()
        == 0
    )

    assert (
        audit.get_events()
        == []
    )


def test_status_is_normalized():
    audit = make_audit()

    event = audit.record(
        event="opened",
        status="open",
        price=100,
    )

    assert (
        event["event"]
        == "OPENED"
    )

    assert (
        event["status"]
        == "OPEN"
    )


def test_reason_is_preserved():
    audit = make_audit()

    event = audit.record_closed(
        price=110,
        realized_pnl=750,
        reason=(
            "Manual paper exit."
        ),
    )

    assert (
        event["reason"]
        == "Manual paper exit."
    )


def test_empty_reason_becomes_none():
    audit = make_audit()

    event = audit.record(
        event="CLOSED",
        price=110,
        reason="   ",
    )

    assert (
        event["reason"]
        is None
    )