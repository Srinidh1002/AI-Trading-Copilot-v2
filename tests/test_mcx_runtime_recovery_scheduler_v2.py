"""PATCH03B runtime recovery + scheduler tests."""

from __future__ import annotations

from pathlib import Path

from mcx import mcx_scheduler
from mcx.mcx_exec_recovery import (
    check_open_position,
    recovery_status,
)


def _open_calendar():
    return {
        "status": "OPEN",
        "tradable": True,
        "new_entries_allowed": True,
        "position_management_allowed": True,
        "note": "regular session",
    }


def _closed_calendar(
    status="CLOSE_BUFFER",
):
    return {
        "status": status,
        "tradable": False,
        "new_entries_allowed": False,
        "position_management_allowed": True,
        "note": "new entries closed",
    }


def test_flat_recovery_backward_compatibility():
    result = recovery_status(
        {
            "active_position": None
        },
        "CRUDEOILM",
    )

    assert (
        result[
            "recovery_required"
        ]
        is False
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is True
    )


def test_open_position_requires_recovery():
    state = {
        "active_position": {
            "trade_id": "T1",
        }
    }

    result = check_open_position(
        state
    )

    assert (
        result[
            "recovery_required"
        ]
        is True
    )

    assert (
        result["mode"]
        == "RECOVERY_ONLY"
    )


def test_closed_calendar_blocks_flat_entry():
    result = recovery_status(
        {
            "active_position": None
        },
        "CRUDEOILM",
        calendar_state=(
            _closed_calendar()
        ),
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        result[
            "position_management_allowed"
        ]
        is False
    )

    assert (
        result[
            "runtime_should_continue"
        ]
        is False
    )


def test_closed_calendar_does_not_strand_open_position():
    result = recovery_status(
        {
            "active_position": {
                "trade_id": "T1",
            }
        },
        "CRUDEOILM",
        calendar_state=(
            _closed_calendar()
        ),
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        result[
            "recovery_required"
        ]
        is True
    )

    assert (
        result[
            "position_management_allowed"
        ]
        is True
    )

    assert (
        result[
            "runtime_should_continue"
        ]
        is True
    )


def test_open_calendar_flat_allows_entry():
    result = recovery_status(
        {
            "active_position": None
        },
        "CRUDEOILM",
        calendar_state=(
            _open_calendar()
        ),
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is True
    )


def test_open_position_blocks_second_entry_even_when_calendar_open():
    result = recovery_status(
        {
            "active_position": {
                "trade_id": "T1",
            }
        },
        "CRUDEOILM",
        calendar_state=(
            _open_calendar()
        ),
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        result[
            "position_management_allowed"
        ]
        is True
    )


def test_scheduler_uses_calendar_for_flat_runtime(
    monkeypatch,
):
    monkeypatch.setattr(
        mcx_scheduler,
        "get_session",
        lambda now=None:
            _closed_calendar(),
    )

    result = (
        mcx_scheduler
        .runtime_permissions(
            has_active_position=False,
        )
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        result[
            "runtime_should_continue"
        ]
        is False
    )


def test_scheduler_keeps_recovery_runtime_alive(
    monkeypatch,
):
    monkeypatch.setattr(
        mcx_scheduler,
        "get_session",
        lambda now=None:
            _closed_calendar(),
    )

    result = (
        mcx_scheduler
        .runtime_permissions(
            has_active_position=True,
        )
    )

    assert (
        result[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        result[
            "position_management_allowed"
        ]
        is True
    )

    assert (
        result[
            "runtime_should_continue"
        ]
        is True
    )


def test_scheduler_remains_manual_only():
    assert (
        mcx_scheduler
        .AUTOMATIC_LAUNCH_ENABLED
        is False
    )


def test_scheduler_is_fyers_only():
    assert (
        mcx_scheduler
        .CANONICAL_DATA_PROVIDER
        == "FYERS"
    )

    tasks = (
        mcx_scheduler
        .pre_open_tasks()
    )

    joined = " ".join(
        tasks
    ).lower()

    assert "fyers" in joined
    assert "angel" not in joined


def test_close_drain_keeps_monitor_and_reconcile_tasks():
    tasks = (
        mcx_scheduler
        .close_drain_tasks()
    )

    assert (
        "block_new_entries"
        in tasks
    )

    assert (
        "monitor_open_positions"
        in tasks
    )

    assert (
        "close_open_positions"
        in tasks
    )

    assert (
        "reconcile_outcomes"
        in tasks
    )


def test_paper_bot_calendar_block_preserves_recovery():
    text = Path(
        "src/mcx/mcx_paper_bot.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "CALENDAR_ENTRY_BLOCKED"
        in text
    )

    assert (
        "existing PAPER position remains"
        in text
    )

    assert (
        "recovery_status("
        in text
    )


def test_paper_bot_entry_has_defense_in_depth():
    text = Path(
        "src/mcx/mcx_paper_bot.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'if not recovery.get('
        in text
    )

    assert (
        '"new_entries_allowed"'
        in text
    )

    assert (
        "ENTRY_BLOCKED:"
        in text
    )


def test_scheduler_contains_no_angel_authority():
    text = Path(
        "src/mcx/mcx_scheduler.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "SmartConnect",
        "SmartApi",
        "ANGEL_API_KEY",
        "ANGEL_USER_ID",
        "ANGEL_PASSWORD",
        "verify_angel_auth",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
