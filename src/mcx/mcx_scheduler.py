"""MCX scheduler/readiness framework.

Automatic launch remains disabled during current certification work.

Scheduler authority:
- calendar controls new-entry eligibility;
- existing positions keep recovery/management authority;
- FYERS is the canonical primary data provider;
- no Angel fallback.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mcx.mcx_calendar import (
    get_session,
)


IST = ZoneInfo(
    "Asia/Kolkata"
)

AUTOMATIC_LAUNCH_ENABLED = False

CANONICAL_DATA_PROVIDER = "FYERS"


def runtime_permissions(
    now=None,
    *,
    has_active_position=False,
):
    """Resolve scheduler permission without launching anything."""

    if now is None:
        now = datetime.now(
            IST
        )

    calendar = get_session(
        now
    )

    calendar_entry_allowed = bool(
        calendar.get(
            "new_entries_allowed",
            calendar.get(
                "tradable",
                False,
            ),
        )
    )

    has_active_position = bool(
        has_active_position
    )

    return {
        "provider":
            CANONICAL_DATA_PROVIDER,
        "automatic_launch_enabled":
            AUTOMATIC_LAUNCH_ENABLED,
        "calendar":
            calendar,
        "calendar_status":
            calendar.get(
                "status"
            ),
        "new_entries_allowed":
            bool(
                calendar_entry_allowed
                and not has_active_position
            ),
        "position_management_allowed":
            has_active_position,
        "recovery_required":
            has_active_position,
        "runtime_should_continue":
            bool(
                calendar_entry_allowed
                or has_active_position
            ),
    }


def _is_session_open(
    now=None,
):
    permissions = (
        runtime_permissions(
            now,
            has_active_position=False,
        )
    )

    return bool(
        permissions[
            "new_entries_allowed"
        ]
    )


def pre_open_tasks():
    """Readiness work only — does not auto-start trading."""

    return [
        "refresh_fyers_instrument_master",
        "verify_fyers_auth",
        "load_authoritative_mcx_calendar",
        "verify_execution_calibration",
        "print_presession_report",
        "health_check",
    ]


def in_session_tasks():
    return [
        "cycle_decision",
        "monitor_positions",
        "log_decisions",
    ]


def close_drain_tasks():
    return [
        "block_new_entries",
        "monitor_open_positions",
        "close_open_positions",
        "reconcile_outcomes",
    ]


def end_of_day_tasks():
    return [
        "final_reconciliation",
        "certification_status",
        "learning_collect",
        "publish_daily_stats",
        "shutdown_when_flat",
    ]


def status(
    now=None,
    *,
    has_active_position=False,
):
    if now is None:
        now = datetime.now(
            IST
        )

    permissions = (
        runtime_permissions(
            now,
            has_active_position=(
                has_active_position
            ),
        )
    )

    calendar = (
        permissions[
            "calendar"
        ]
    )

    return {
        "time":
            now.isoformat(
                timespec="seconds"
            ),
        "provider":
            CANONICAL_DATA_PROVIDER,
        "automatic_launch_enabled":
            AUTOMATIC_LAUNCH_ENABLED,
        "calendar_status":
            calendar.get(
                "status"
            ),
        "calendar_note":
            calendar.get(
                "note"
            ),
        "new_entries_allowed":
            permissions[
                "new_entries_allowed"
            ],
        "position_management_allowed":
            permissions[
                "position_management_allowed"
            ],
        "recovery_required":
            permissions[
                "recovery_required"
            ],
        "runtime_should_continue":
            permissions[
                "runtime_should_continue"
            ],
    }


if __name__ == "__main__":
    print(
        "mcx_scheduler module loaded OK"
    )

    print(
        status()
    )
