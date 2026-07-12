"""
Tests for persistent paper-trade state repository.

The repository is responsible only for storing and
recovering paper-trade state dictionaries.

These tests verify:
- save and recovery
- state updates
- batch persistence
- OPEN/CLOSED filtering
- defensive copies
- validation
- corrupted repository handling
- schema validation
- atomic-write safety
- deletion and counts

Paper trading only.
No broker APIs or real orders are involved.
"""

import json
from unittest.mock import patch

import pytest

from services.paper_trade_repository import (
    PaperTradeRepository,
)


# ============================================================
# HELPERS
# ============================================================


def make_trade_state(
    trade_id="paper-001",
    status="OPEN",
    current_price=110.0,
):
    """
    Build a deterministic paper-trade state dictionary.
    """

    return {
        "trade_id": trade_id,
        "status": status,
        "underlying": "NIFTY",
        "exchange": "NSE",
        "symboltoken": "99926000",
        "option_symbol": "NIFTY_TEST_CE",
        "option_type": "CE",
        "strike": 24200.0,
        "expiry": "2026-07-30",
        "entry_price": 100.0,
        "current_price": current_price,
        "stop_loss": 80.0,
        "target": 140.0,
        "quantity": 75,
        "lot_size": 75,
        "lots": 1,
        "status": status,
        "unrealized_pnl": 750.0,
        "realized_pnl": None,
        "exit_price": None,
        "exit_reason": None,
        "opened_at": (
            "2026-07-12T09:15:00+00:00"
        ),
        "closed_at": None,
        "source_decision_id": "decision-001",
        "source_audit_ref": "audit-001",
        "metadata": {
            "test": True,
        },
    }


def make_closed_trade_state(
    trade_id="paper-closed-001",
):
    """
    Build a deterministic CLOSED paper-trade state.
    """

    state = make_trade_state(
        trade_id=trade_id,
        status="CLOSED",
        current_price=140.0,
    )

    state.update(
        {
            "unrealized_pnl": 0.0,
            "realized_pnl": 3000.0,
            "exit_price": 140.0,
            "exit_reason": "TARGET",
            "closed_at": (
                "2026-07-12T10:00:00+00:00"
            ),
        }
    )

    return state


# ============================================================
# CONSTRUCTION
# ============================================================


def test_default_file_path():

    repository = PaperTradeRepository()

    assert str(
        repository.file_path
    ).replace(
        "\\",
        "/",
    ).endswith(
        "data/paper_trading/"
        "paper_trade_state.json"
    )


def test_custom_file_path(
    tmp_path,
):

    file_path = (
        tmp_path
        / "custom.json"
    )

    repository = (
        PaperTradeRepository(
            file_path=file_path,
        )
    )

    assert (
        repository.file_path
        == file_path
    )


# ============================================================
# MISSING / EMPTY REPOSITORY
# ============================================================


def test_missing_repository_returns_no_trades(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "missing.json"
        )
    )

    assert (
        repository.get_all_trades()
        == []
    )

    assert (
        repository.count_trades()
        == 0
    )


def test_missing_trade_returns_none(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    assert (
        repository.get_trade(
            "does-not-exist"
        )
        is None
    )


def test_missing_trade_does_not_exist(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    assert (
        repository.exists(
            "missing"
        )
        is False
    )


# ============================================================
# SAVE ONE TRADE
# ============================================================


def test_save_trade_creates_repository_file(
    tmp_path,
):

    file_path = (
        tmp_path
        / "nested"
        / "paper"
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    repository.save_trade(
        make_trade_state()
    )

    assert file_path.exists()


def test_save_trade_returns_saved_state(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    state = make_trade_state()

    result = (
        repository.save_trade(
            state
        )
    )

    assert result == state


def test_save_and_recover_trade(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    state = make_trade_state()

    repository.save_trade(
        state
    )

    recovered = (
        repository.get_trade(
            state["trade_id"]
        )
    )

    assert recovered == state


def test_saved_trade_exists(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state(
            trade_id="paper-exists"
        )
    )

    assert (
        repository.exists(
            "paper-exists"
        )
        is True
    )


def test_save_trade_updates_existing_state(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    original = make_trade_state(
        trade_id="paper-update",
        current_price=100.0,
    )

    repository.save_trade(
        original
    )

    updated = make_trade_state(
        trade_id="paper-update",
        current_price=125.0,
    )

    updated[
        "unrealized_pnl"
    ] = 1875.0

    repository.save_trade(
        updated
    )

    recovered = (
        repository.get_trade(
            "paper-update"
        )
    )

    assert (
        recovered[
            "current_price"
        ]
        == 125.0
    )

    assert (
        recovered[
            "unrealized_pnl"
        ]
        == 1875.0
    )

    assert (
        repository.count_trades()
        == 1
    )


# ============================================================
# MULTIPLE TRADES
# ============================================================


def test_save_multiple_individual_trades(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state(
            trade_id="paper-1"
        )
    )

    repository.save_trade(
        make_trade_state(
            trade_id="paper-2"
        )
    )

    assert (
        repository.count_trades()
        == 2
    )


def test_save_trades_batch(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    states = [
        make_trade_state(
            trade_id="paper-1"
        ),
        make_trade_state(
            trade_id="paper-2"
        ),
        make_closed_trade_state(
            trade_id="paper-3"
        ),
    ]

    result = (
        repository.save_trades(
            states
        )
    )

    assert result == states

    assert (
        repository.count_trades()
        == 3
    )


def test_batch_save_preserves_existing_trades(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state(
            trade_id="existing"
        )
    )

    repository.save_trades(
        [
            make_trade_state(
                trade_id="new-1"
            ),
            make_trade_state(
                trade_id="new-2"
            ),
        ]
    )

    assert (
        repository.count_trades()
        == 3
    )

    assert (
        repository.exists(
            "existing"
        )
        is True
    )


def test_empty_batch_is_allowed(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    result = (
        repository.save_trades(
            []
        )
    )

    assert result == []

    assert (
        repository.count_trades()
        == 0
    )


# ============================================================
# OPEN / CLOSED RECOVERY
# ============================================================


def test_get_open_trades(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trades(
        [
            make_trade_state(
                trade_id="open-1"
            ),
            make_trade_state(
                trade_id="open-2"
            ),
            make_closed_trade_state(
                trade_id="closed-1"
            ),
        ]
    )

    open_trades = (
        repository.get_open_trades()
    )

    assert len(
        open_trades
    ) == 2

    assert {
        trade["trade_id"]
        for trade in open_trades
    } == {
        "open-1",
        "open-2",
    }


def test_get_closed_trades(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trades(
        [
            make_trade_state(
                trade_id="open-1"
            ),
            make_closed_trade_state(
                trade_id="closed-1"
            ),
            make_closed_trade_state(
                trade_id="closed-2"
            ),
        ]
    )

    closed_trades = (
        repository.get_closed_trades()
    )

    assert len(
        closed_trades
    ) == 2

    assert {
        trade["trade_id"]
        for trade in closed_trades
    } == {
        "closed-1",
        "closed-2",
    }


def test_status_filter_is_case_insensitive(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    lower_open = make_trade_state(
        trade_id="lower-open",
        status="open",
    )

    lower_closed = (
        make_closed_trade_state(
            trade_id="lower-closed"
        )
    )

    lower_closed[
        "status"
    ] = "closed"

    repository.save_trades(
        [
            lower_open,
            lower_closed,
        ]
    )

    assert (
        repository.count_open_trades()
        == 1
    )

    assert (
        repository.count_closed_trades()
        == 1
    )


# ============================================================
# COUNTS
# ============================================================


def test_trade_counts(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trades(
        [
            make_trade_state(
                trade_id="open-1"
            ),
            make_trade_state(
                trade_id="open-2"
            ),
            make_closed_trade_state(
                trade_id="closed-1"
            ),
        ]
    )

    assert (
        repository.count_trades()
        == 3
    )

    assert (
        repository.count_open_trades()
        == 2
    )

    assert (
        repository.count_closed_trades()
        == 1
    )


# ============================================================
# DEFENSIVE COPIES
# ============================================================


def test_save_trade_does_not_mutate_input(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    state = make_trade_state()

    original = json.loads(
        json.dumps(
            state
        )
    )

    repository.save_trade(
        state
    )

    assert state == original


def test_save_trade_return_is_defensive_copy(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    result = (
        repository.save_trade(
            make_trade_state()
        )
    )

    result[
        "metadata"
    ][
        "test"
    ] = False

    recovered = (
        repository.get_trade(
            "paper-001"
        )
    )

    assert (
        recovered[
            "metadata"
        ][
            "test"
        ]
        is True
    )


def test_get_trade_returns_defensive_copy(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state()
    )

    first = (
        repository.get_trade(
            "paper-001"
        )
    )

    first[
        "current_price"
    ] = 999999

    second = (
        repository.get_trade(
            "paper-001"
        )
    )

    assert (
        second[
            "current_price"
        ]
        == 110.0
    )


def test_get_all_trades_returns_defensive_copies(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state()
    )

    trades = (
        repository.get_all_trades()
    )

    trades[0][
        "metadata"
    ][
        "test"
    ] = False

    recovered = (
        repository.get_trade(
            "paper-001"
        )
    )

    assert (
        recovered[
            "metadata"
        ][
            "test"
        ]
        is True
    )


# ============================================================
# TRADE VALIDATION
# ============================================================


def test_save_trade_requires_dictionary(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        TypeError,
        match="dictionary",
    ):
        repository.save_trade(
            "not-a-dictionary"
        )


def test_save_trade_requires_trade_id(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="trade_id",
    ):
        repository.save_trade(
            {
                "status": "OPEN",
            }
        )


def test_save_trade_rejects_empty_trade_id(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        repository.save_trade(
            {
                "trade_id": "   ",
                "status": "OPEN",
            }
        )


def test_get_trade_rejects_empty_trade_id(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        repository.get_trade(
            ""
        )


def test_save_trades_requires_list_or_tuple(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        TypeError,
        match="list or tuple",
    ):
        repository.save_trades(
            {
                "trade_id": "paper-1",
            }
        )


def test_batch_rejects_duplicate_trade_ids(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="Duplicate trade_id",
    ):
        repository.save_trades(
            [
                make_trade_state(
                    trade_id="duplicate"
                ),
                make_trade_state(
                    trade_id="duplicate"
                ),
            ]
        )


def test_invalid_batch_does_not_create_file(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
    ):
        repository.save_trades(
            [
                make_trade_state(
                    trade_id="valid"
                ),
                {
                    "status": "OPEN",
                },
            ]
        )

    assert (
        file_path.exists()
        is False
    )


# ============================================================
# FILE FORMAT / SCHEMA
# ============================================================


def test_repository_writes_expected_schema(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    repository.save_trade(
        make_trade_state()
    )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        document = json.load(
            file
        )

    assert (
        document["version"]
        == 1
    )

    assert (
        "trades"
        in document
    )

    assert (
        "paper-001"
        in document["trades"]
    )


def test_invalid_json_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="Invalid JSON",
    ):
        repository.get_all_trades()


def test_non_object_repository_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        "[]",
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="JSON object",
    ):
        repository.get_all_trades()


def test_unsupported_schema_version_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "version": 999,
                "trades": {},
            }
        ),
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        repository.get_all_trades()


def test_missing_version_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "trades": {},
            }
        ),
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="version",
    ):
        repository.get_all_trades()


def test_invalid_trades_container_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "version": 1,
                "trades": [],
            }
        ),
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="must be a dictionary",
    ):
        repository.get_all_trades()


def test_repository_key_mismatch_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "version": 1,
                "trades": {
                    "paper-A": {
                        "trade_id": "paper-B",
                        "status": "OPEN",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        repository.get_all_trades()


# ============================================================
# DELETE
# ============================================================


def test_delete_existing_trade(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trade(
        make_trade_state(
            trade_id="delete-me"
        )
    )

    result = (
        repository.delete_trade(
            "delete-me"
        )
    )

    assert result is True

    assert (
        repository.exists(
            "delete-me"
        )
        is False
    )

    assert (
        repository.count_trades()
        == 0
    )


def test_delete_missing_trade_returns_false(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    result = (
        repository.delete_trade(
            "missing"
        )
    )

    assert result is False


def test_delete_one_trade_preserves_others(
    tmp_path,
):

    repository = (
        PaperTradeRepository(
            tmp_path
            / "state.json"
        )
    )

    repository.save_trades(
        [
            make_trade_state(
                trade_id="keep"
            ),
            make_trade_state(
                trade_id="delete"
            ),
        ]
    )

    repository.delete_trade(
        "delete"
    )

    assert (
        repository.exists(
            "keep"
        )
        is True
    )

    assert (
        repository.exists(
            "delete"
        )
        is False
    )


# ============================================================
# ATOMIC WRITE SAFETY
# ============================================================


def test_successful_write_leaves_no_temp_file(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    repository.save_trade(
        make_trade_state()
    )

    temporary_path = (
        file_path.with_name(
            file_path.name
            + ".tmp"
        )
    )

    assert file_path.exists()

    assert (
        temporary_path.exists()
        is False
    )


def test_replace_failure_cleans_temp_file(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    temporary_path = (
        file_path.with_name(
            file_path.name
            + ".tmp"
        )
    )

    with patch(
        "services.paper_trade_repository."
        "os.replace",
        side_effect=OSError(
            "Replace failed."
        ),
    ):
        with pytest.raises(
            OSError,
            match="Replace failed",
        ):
            repository.save_trade(
                make_trade_state()
            )

    assert (
        temporary_path.exists()
        is False
    )


def test_failed_update_preserves_existing_repository(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    repository = (
        PaperTradeRepository(
            file_path
        )
    )

    original = make_trade_state(
        trade_id="paper-safe",
        current_price=100.0,
    )

    repository.save_trade(
        original
    )

    updated = make_trade_state(
        trade_id="paper-safe",
        current_price=130.0,
    )

    with patch(
        "services.paper_trade_repository."
        "os.replace",
        side_effect=OSError(
            "Replace failed."
        ),
    ):
        with pytest.raises(
            OSError,
        ):
            repository.save_trade(
                updated
            )

    recovered = (
        repository.get_trade(
            "paper-safe"
        )
    )

    assert (
        recovered[
            "current_price"
        ]
        == 100.0
    )


# ============================================================
# RESTART / RECOVERY SIMULATION
# ============================================================


def test_new_repository_instance_recovers_saved_trade(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    first_repository = (
        PaperTradeRepository(
            file_path
        )
    )

    first_repository.save_trade(
        make_trade_state(
            trade_id="restart-test"
        )
    )

    second_repository = (
        PaperTradeRepository(
            file_path
        )
    )

    recovered = (
        second_repository.get_trade(
            "restart-test"
        )
    )

    assert recovered is not None

    assert (
        recovered["trade_id"]
        == "restart-test"
    )

    assert (
        recovered["status"]
        == "OPEN"
    )


def test_restart_recovers_open_and_closed_trades(
    tmp_path,
):

    file_path = (
        tmp_path
        / "state.json"
    )

    first_repository = (
        PaperTradeRepository(
            file_path
        )
    )

    first_repository.save_trades(
        [
            make_trade_state(
                trade_id="open-after-restart"
            ),
            make_closed_trade_state(
                trade_id="closed-after-restart"
            ),
        ]
    )

    recovered_repository = (
        PaperTradeRepository(
            file_path
        )
    )

    assert (
        recovered_repository
        .count_open_trades()
        == 1
    )

    assert (
        recovered_repository
        .count_closed_trades()
        == 1
    )

    assert (
        recovered_repository
        .count_trades()
        == 2
    )