import sys

sys.path.insert(0, "src")

from mcx.mcx_certification import (
    evaluate_diversity,
    status,
    update_counters,
)
from mcx.mcx_paper_bot import (
    certification_target_reached,
)


def test_first_100_is_hard_cap_and_101_cannot_repair():
    state = {
        "product": "CRUDEOILM",
        "epoch": "POST_PRECISION_V4",
        "t1_hit_wins": 79,
        "sl_losses": 21,
        "_counted_trade_ids": [
            f"T{i:03d}"
            for i in range(1, 101)
        ],
        "_cert_rejected_trade_ids": [],
        "completed_trades": [],
    }

    before = status(state)

    assert (
        before["total_countable_trades"]
        == 100
    )
    assert before["passes_threshold"] is False

    trade_101 = {
        "trade_id": "T101",
        "product": "CRUDEOILM",
        "certification_eligible": True,
        "first_touch_result": "T1_FIRST",
        "entry_time": "2026-09-17T10:00:00",
    }

    update_counters(
        state,
        trade_101,
    )

    after = status(state)

    assert (
        after["total_countable_trades"]
        == 100
    )
    assert after["t1_hit_wins"] == 79
    assert after["sl_losses"] == 21
    assert after["passes_threshold"] is False

    assert (
        trade_101["_counter_rejected"]
        == "CERTIFICATION_FIRST_100_COMPLETE"
    )

    assert (
        "T101"
        not in state["_counted_trade_ids"]
    )


def test_status_requires_exactly_100_not_more():
    exact = {
        "t1_hit_wins": 80,
        "sl_losses": 20,
        "completed_trades": [],
        "_counted_trade_ids": [],
    }

    over = {
        "t1_hit_wins": 81,
        "sl_losses": 20,
        "completed_trades": [],
        "_counted_trade_ids": [],
    }

    assert status(
        exact
    )["passes_threshold"] is True

    assert status(
        over
    )["passes_threshold"] is False


def test_41st_same_day_trade_is_rejected():
    completed = [
        {
            "trade_id": f"D1_{i:02d}",
            "entry_time":
                f"2026-09-16T10:{i % 60:02d}:00",
            "regime_at_entry": "TRENDING",
            "countable": True,
            "certification_eligible": True,
            "first_touch_result": "T1_FIRST",
        }
        for i in range(1, 41)
    ]

    state = {
        "product": "CRUDEOILM",
        "epoch": "POST_PRECISION_V4",
        "t1_hit_wins": 40,
        "sl_losses": 0,
        "_counted_trade_ids": [
            x["trade_id"]
            for x in completed
        ],
        "_cert_rejected_trade_ids": [],
        "completed_trades": completed,
    }

    trade_41 = {
        "trade_id": "D1_41",
        "product": "CRUDEOILM",
        "certification_eligible": True,
        "first_touch_result": "T1_FIRST",
        "entry_time": "2026-09-16T11:30:00",
    }

    update_counters(
        state,
        trade_41,
    )

    assert (
        status(state)["total_countable_trades"]
        == 40
    )

    assert (
        trade_41["_counter_rejected"]
        == "DAILY_COUNTABLE_CAP_REACHED"
    )

    assert (
        "D1_41"
        not in state["_counted_trade_ids"]
    )


def test_noncountable_completed_trades_do_not_create_diversity():
    times = (
        "2026-09-01T10:00:00",
        "2026-09-02T18:00:00",
        "2026-09-03T10:00:00",
        "2026-09-04T18:00:00",
        "2026-09-05T10:00:00",
    )

    completed = [
        {
            "trade_id": f"NC{i}",
            "entry_time": ts,
            "regime_at_entry":
                "TRENDING"
                if i % 2
                else "RANGE_BOUND",
            "countable": False,
            "certification_eligible": False,
            "first_touch_result": "AMBIGUOUS",
        }
        for i, ts in enumerate(
            times,
            1,
        )
    ]

    state = {
        "completed_trades": completed,
        "_counted_trade_ids": [],
    }

    passed, details = evaluate_diversity(
        state
    )

    assert passed is False

    assert details == {
        "distinct_days": 0,
        "distinct_regimes": 0,
        "distinct_phases": 0,
        "max_per_day": 0,
    }


def test_diversity_uses_only_counted_trade_ids():
    completed = [
        {
            "trade_id": "C1",
            "entry_time": "2026-09-01T10:00:00",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "C2",
            "entry_time": "2026-09-02T18:00:00",
            "regime_at_entry": "RANGE_BOUND",
        },
        {
            "trade_id": "C3",
            "entry_time": "2026-09-03T10:00:00",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "C4",
            "entry_time": "2026-09-04T18:00:00",
            "regime_at_entry": "RANGE_BOUND",
        },
        {
            "trade_id": "C5",
            "entry_time": "2026-09-05T10:00:00",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "NC_EXTRA",
            "entry_time": "2026-09-06T18:00:00",
            "regime_at_entry": "OTHER",
            "countable": False,
        },
    ]

    state = {
        "completed_trades": completed,
        "_counted_trade_ids": [
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
        ],
    }

    passed, details = evaluate_diversity(
        state
    )

    assert passed is True
    assert details["distinct_days"] == 5
    assert details["distinct_regimes"] == 2
    assert details["distinct_phases"] == 2
    assert details["max_per_day"] == 1


def test_runner_stops_when_fixed_sample_reaches_100():
    at_99 = {
        "product": "CRUDEOILM",
        "t1_hit_wins": 79,
        "sl_losses": 20,
    }

    at_100_failed = {
        "product": "CRUDEOILM",
        "t1_hit_wins": 79,
        "sl_losses": 21,
    }

    assert (
        certification_target_reached(
            at_99,
            "CRUDEOILM",
        )
        is False
    )

    assert (
        certification_target_reached(
            at_100_failed,
            "CRUDEOILM",
        )
        is True
    )

    # PRECERT products must not be governed by /100.
    assert (
        certification_target_reached(
            at_100_failed,
            "GOLDM",
        )
        is False
    )
