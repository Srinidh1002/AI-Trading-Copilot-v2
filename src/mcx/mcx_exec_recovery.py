"""MCX restart/recovery authority.

Core rule:
- an open PAPER position always keeps runtime recovery/management authority;
- calendar state may block NEW entries;
- calendar state must never strand an existing PAPER position.
"""

from __future__ import annotations


def check_open_position(state):
    """Return explicit recovery requirement."""

    position = (
        (state or {})
        .get("active_position")
    )

    if not position:
        return {
            "recovery_required": False,
            "mode": "NORMAL",
            "position": None,
        }

    return {
        "recovery_required": True,
        "mode": "RECOVERY_ONLY",
        "position": position,
    }


def recovery_status(
    state,
    product,
    calendar_state=None,
):
    """Resolve runtime permissions.

    Backward compatibility:
    without calendar_state, a flat state still allows new entries.

    With calendar_state:
    calendar authority governs NEW entries only.
    Existing-position management remains enabled.
    """

    recovery = (
        check_open_position(
            state
        )
    )

    has_position = bool(
        recovery[
            "recovery_required"
        ]
    )

    if calendar_state is None:
        calendar_new_entries_allowed = True
        calendar_status = None

    else:
        calendar_status = (
            calendar_state.get(
                "status"
            )
        )

        calendar_new_entries_allowed = bool(
            calendar_state.get(
                "new_entries_allowed",
                calendar_state.get(
                    "tradable",
                    False,
                ),
            )
        )

    new_entries_allowed = bool(
        (not has_position)
        and calendar_new_entries_allowed
    )

    return {
        "product": product,
        "mode": (
            "RECOVERY_ONLY"
            if has_position
            else "NORMAL"
        ),
        "recovery_required":
            has_position,
        "position":
            recovery.get(
                "position"
            ),
        "calendar_status":
            calendar_status,
        "calendar_new_entries_allowed":
            calendar_new_entries_allowed,
        "new_entries_allowed":
            new_entries_allowed,

        # Critical invariant:
        # a position that already exists remains manageable even when
        # calendar authority blocks new entries.
        "position_management_allowed":
            has_position,

        "runtime_should_continue":
            bool(
                has_position
                or calendar_new_entries_allowed
            ),
    }


if __name__ == "__main__":
    print(
        recovery_status(
            {
                "active_position": {
                    "trade_id": "T1"
                }
            },
            "CRUDEOILM",
            calendar_state={
                "status": "CLOSE_BUFFER",
                "new_entries_allowed":
                    False,
            },
        )
    )
