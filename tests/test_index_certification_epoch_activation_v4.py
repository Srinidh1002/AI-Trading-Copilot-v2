from copy import deepcopy
from pathlib import Path

import pytest

from target_focused_bot import (
    CERTIFICATION_EPOCH,
    STRATEGY_VERSION,
    UnifiedTradingBot,
)


def _legacy_bot():
    bot = UnifiedTradingBot.__new__(UnifiedTradingBot)

    bot.strategy_version = None
    bot.certification_epoch = None
    bot.is_legacy_precert = True

    bot.active_trades = {}
    bot.certification_counter = 0
    bot.certification_wins = 0
    bot.certification_losses = 0
    bot.counted_trade_ids = set()

    bot.completed_trades = [
        {
            "trade_id": "LEGACY_DIAGNOSTIC_1",
            "status": "CLOSED",
            "strategy_version": None,
            "certification_epoch": None,
            "certification_counted": False,
        }
    ]

    snapshots = []

    def fake_save_state():
        snapshots.append(
            {
                "strategy_version": bot.strategy_version,
                "certification_epoch": bot.certification_epoch,
                "completed_trades": deepcopy(bot.completed_trades),
                "counter": bot.certification_counter,
                "counted_trade_ids": set(bot.counted_trade_ids),
            }
        )

    bot.save_state = fake_save_state

    return bot, snapshots


def test_flat_legacy_state_activates_prospectively_without_relabeling_history():
    bot, snapshots = _legacy_bot()

    historical_before = deepcopy(bot.completed_trades)

    result = bot.activate_current_certification_epoch_if_safe()

    assert result["status"] == "ACTIVATED"
    assert result["changed"] is True

    assert bot.strategy_version == STRATEGY_VERSION
    assert bot.certification_epoch == CERTIFICATION_EPOCH
    assert bot.is_legacy_precert is False

    assert bot.certification_counter == 0
    assert bot.certification_wins == 0
    assert bot.certification_losses == 0
    assert bot.counted_trade_ids == set()

    # Existing diagnostic trades must never be rewritten into the new epoch.
    assert bot.completed_trades == historical_before
    assert bot.completed_trades[0]["strategy_version"] is None
    assert bot.completed_trades[0]["certification_epoch"] is None

    assert len(snapshots) == 1
    assert snapshots[0]["strategy_version"] == STRATEGY_VERSION
    assert snapshots[0]["certification_epoch"] == CERTIFICATION_EPOCH
    assert snapshots[0]["completed_trades"] == historical_before


@pytest.mark.parametrize(
    ("field", "value", "expected_blocker"),
    [
        (
            "active_trades",
            {"OPEN_1": {"trade_id": "OPEN_1"}},
            "ACTIVE_TRADES_PRESENT",
        ),
        (
            "certification_counter",
            1,
            "CERTIFICATION_COUNTER_NONZERO",
        ),
        (
            "certification_wins",
            1,
            "CERTIFICATION_WINS_NONZERO",
        ),
        (
            "certification_losses",
            1,
            "CERTIFICATION_LOSSES_NONZERO",
        ),
        (
            "counted_trade_ids",
            {"OLD_COUNTED"},
            "COUNTED_TRADE_IDS_PRESENT",
        ),
    ],
)
def test_unsafe_legacy_state_blocks_activation(
    field,
    value,
    expected_blocker,
):
    bot, snapshots = _legacy_bot()

    setattr(
        bot,
        field,
        value,
    )

    result = bot.activate_current_certification_epoch_if_safe()

    assert result["status"] == "BLOCKED"
    assert result["changed"] is False
    assert result["reason"] == "UNSAFE_PRECERT_STATE"
    assert expected_blocker in result["blockers"]

    assert bot.strategy_version is None
    assert bot.certification_epoch is None
    assert bot.is_legacy_precert is True
    assert snapshots == []


def test_current_authority_is_idempotent_and_does_not_rewrite_state():
    bot, snapshots = _legacy_bot()

    bot.strategy_version = STRATEGY_VERSION
    bot.certification_epoch = CERTIFICATION_EPOCH
    bot.is_legacy_precert = False

    result = bot.activate_current_certification_epoch_if_safe()

    assert result["status"] == "CURRENT"
    assert result["changed"] is False
    assert snapshots == []


def test_stale_nonlegacy_authority_fails_closed():
    bot, snapshots = _legacy_bot()

    bot.strategy_version = "OLD_STRATEGY"
    bot.certification_epoch = "OLD_EPOCH"
    bot.is_legacy_precert = False

    result = bot.activate_current_certification_epoch_if_safe()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "NONLEGACY_AUTHORITY_MISMATCH"
    assert snapshots == []


@pytest.mark.parametrize(
    "runner_name",
    [
        "run_nifty.py",
        "run_sensex.py",
    ],
)
def test_root_launcher_activates_or_verifies_epoch_before_session(
    runner_name,
):
    repo = Path(__file__).resolve().parents[1]

    text = (repo / runner_name).read_text(encoding="utf-8")

    load_index = text.index("bot.load_state()")

    activation_index = text.index("bot.activate_current_certification_epoch_if_safe()")

    run_index = text.index("bot.run_single_session()")

    assert load_index < activation_index < run_index

    assert '("CURRENT", "ACTIVATED")' in text


@pytest.mark.parametrize(
    "runner_name",
    [
        "run_nifty.py",
        "run_sensex.py",
    ],
)
def test_primary_provider_connect_failure_is_fail_closed(runner_name):
    repo = Path(__file__).resolve().parents[1]
    text = (repo / runner_name).read_text(encoding="utf-8")

    guard = "if not bot.connect_with_retry():"
    stop = 'raise SystemExit("STARTUP_BLOCKED: PRIMARY_PROVIDER_CONNECTION_FAILED")'
    load_instruments = "bot.load_instruments()"
    run_session = "bot.run_single_session()"

    guard_index = text.index(guard)
    stop_index = text.index(stop)
    load_index = text.index(load_instruments)
    run_index = text.index(run_session)

    assert guard_index < stop_index < load_index < run_index
