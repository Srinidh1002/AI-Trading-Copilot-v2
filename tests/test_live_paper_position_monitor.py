import copy

import pytest

from services.live_paper_position_monitor import (
    LivePaperPositionMonitor,
)


# ============================================================
# FAKES
# ============================================================


class FakeMarketDataClient:

    def get_market_data(
        self,
        mode,
        exchange_tokens,
    ):
        return {
            "data": {
                "fetched": [
                    {
                        "ltp": 120.0
                    }
                ]
            }
        }


class FakeRepository:
    pass


class FakePaperTradingEngine:

    def __init__(
        self,
        recovered=None,
    ):
        self.recovered = (
            recovered
            if recovered is not None
            else []
        )

        self.recover_calls = []

        self.open_count = 2
        self.closed_count = 1
        self.total_count = 3

    def recover_trades(
        self,
        include_closed=True,
    ):
        self.recover_calls.append(
            include_closed
        )

        return copy.deepcopy(
            self.recovered
        )

    def count_open_trades(
        self,
    ):
        return self.open_count

    def count_closed_trades(
        self,
    ):
        return self.closed_count

    def count_trades(
        self,
    ):
        return self.total_count


class FakeLifecycleRunner:

    def __init__(
        self,
        report=None,
    ):
        self.report = (
            report
            if report is not None
            else {
                "status": "COMPLETED",
                "updated_at": (
                    "2026-07-13T10:00:00+00:00"
                ),
                "open_trades_found": 2,
                "processed": 2,
                "failed": 0,
                "open_trades_after": 1,
                "closed_trades_after": 2,
                "results": [
                    {
                        "trade_id": "paper-1",
                        "status": "PROCESSED",
                    },
                    {
                        "trade_id": "paper-2",
                        "status": "PROCESSED",
                    },
                ],
            }
        )

        self.calls = []

    def run_once(
        self,
        *,
        updated_at=None,
    ):
        self.calls.append(
            updated_at
        )

        result = copy.deepcopy(
            self.report
        )

        if updated_at is not None:
            result[
                "updated_at"
            ] = updated_at

        return result


# ============================================================
# HELPERS
# ============================================================


def make_monitor(
    *,
    recovered=None,
    report=None,
    recover_on_start=True,
):

    client = (
        FakeMarketDataClient()
    )

    repository = (
        FakeRepository()
    )

    engine = (
        FakePaperTradingEngine(
            recovered=recovered
        )
    )

    price_provider = (
        lambda trade: 120.0
    )

    runner = (
        FakeLifecycleRunner(
            report=report
        )
    )

    monitor = (
        LivePaperPositionMonitor(
            market_data_client=client,
            repository=repository,
            paper_trading_engine=engine,
            price_provider=price_provider,
            lifecycle_runner=runner,
            recover_on_start=(
                recover_on_start
            ),
        )
    )

    return (
        monitor,
        engine,
        runner,
    )


# ============================================================
# CONSTRUCTOR
# ============================================================


def test_requires_market_data_client():

    with pytest.raises(
        ValueError
    ):
        LivePaperPositionMonitor(
            market_data_client=None
        )


def test_accepts_injected_dependencies():

    monitor, engine, runner = (
        make_monitor()
    )

    assert (
        monitor.paper_trading_engine
        is engine
    )

    assert (
        monitor.lifecycle_runner
        is runner
    )


def test_recover_on_start_defaults_true():

    monitor, _, _ = (
        make_monitor()
    )

    assert (
        monitor.recover_on_start
        is True
    )


def test_recover_on_start_can_be_disabled():

    monitor, _, _ = (
        make_monitor(
            recover_on_start=False
        )
    )

    assert (
        monitor.recover_on_start
        is False
    )


# ============================================================
# RECOVERY
# ============================================================


def test_recover_calls_engine():

    monitor, engine, _ = (
        make_monitor(
            recovered=[
                {
                    "trade_id": "paper-1"
                }
            ]
        )
    )

    recovered = (
        monitor.recover()
    )

    assert (
        engine.recover_calls
        == [
            True
        ]
    )

    assert (
        len(
            recovered
        )
        == 1
    )


def test_recover_marks_monitor_recovered():

    monitor, _, _ = (
        make_monitor()
    )

    monitor.recover()

    assert (
        monitor._recovered
        is True
    )


def test_recover_tracks_count():

    monitor, _, _ = (
        make_monitor(
            recovered=[
                {
                    "trade_id": "1"
                },
                {
                    "trade_id": "2"
                },
            ]
        )
    )

    monitor.recover()

    assert (
        monitor._recovered_trade_count
        == 2
    )


def test_recover_none_becomes_empty_list():

    monitor, engine, _ = (
        make_monitor()
    )

    engine.recovered = None

    recovered = (
        monitor.recover()
    )

    assert (
        recovered
        == []
    )


def test_recover_rejects_invalid_response():

    monitor, engine, _ = (
        make_monitor()
    )

    engine.recovered = {
        "invalid": True
    }

    with pytest.raises(
        ValueError
    ):
        monitor.recover()


def test_recovered_result_is_copy():

    source = [
        {
            "trade_id": "paper-1"
        }
    ]

    monitor, _, _ = (
        make_monitor(
            recovered=source
        )
    )

    result = (
        monitor.recover()
    )

    result[0][
        "trade_id"
    ] = "MUTATED"

    assert (
        source[0][
            "trade_id"
        ]
        == "paper-1"
    )


# ============================================================
# RUN ONCE
# ============================================================


def test_run_once_performs_recovery():

    monitor, engine, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "recovery_performed"
        ]
        is True
    )

    assert (
        len(
            engine.recover_calls
        )
        == 1
    )


def test_run_once_recovers_only_once():

    monitor, engine, _ = (
        make_monitor()
    )

    first = (
        monitor.run_once()
    )

    second = (
        monitor.run_once()
    )

    assert (
        first[
            "recovery_performed"
        ]
        is True
    )

    assert (
        second[
            "recovery_performed"
        ]
        is False
    )

    assert (
        len(
            engine.recover_calls
        )
        == 1
    )


def test_run_without_recovery():

    monitor, engine, _ = (
        make_monitor(
            recover_on_start=False
        )
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "recovery_performed"
        ]
        is False
    )

    assert (
        engine.recover_calls
        == []
    )


def test_run_passes_timestamp():

    monitor, _, runner = (
        make_monitor()
    )

    timestamp = (
        "2026-07-13T11:00:00+00:00"
    )

    monitor.run_once(
        updated_at=timestamp
    )

    assert (
        runner.calls
        == [
            timestamp
        ]
    )


def test_run_returns_status():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )


def test_run_returns_processed_count():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "processed"
        ]
        == 2
    )


def test_run_returns_failed_count():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "failed"
        ]
        == 0
    )


def test_run_returns_open_trades_found():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "open_trades_found"
        ]
        == 2
    )


def test_run_returns_open_trades_after():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "open_trades_after"
        ]
        == 1
    )


def test_run_returns_closed_trades_after():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "closed_trades_after"
        ]
        == 2
    )


def test_run_returns_results():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run_once()
    )

    assert (
        len(
            result[
                "results"
            ]
        )
        == 2
    )


def test_run_results_are_copied():

    report = {
        "status": "COMPLETED",
        "results": [
            {
                "trade_id": "paper-1"
            }
        ],
    }

    monitor, _, runner = (
        make_monitor(
            report=report
        )
    )

    result = (
        monitor.run_once()
    )

    result[
        "results"
    ][0][
        "trade_id"
    ] = "MUTATED"

    assert (
        runner.report[
            "results"
        ][0][
            "trade_id"
        ]
        == "paper-1"
    )


def test_run_alias():

    monitor, _, _ = (
        make_monitor()
    )

    result = (
        monitor.run()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )


def test_invalid_lifecycle_report_rejected():

    monitor, _, runner = (
        make_monitor()
    )

    runner.report = [
        "invalid"
    ]

    with pytest.raises(
        ValueError
    ):
        monitor.run_once()


# ============================================================
# ERROR STATUS
# ============================================================


def test_completed_with_errors_preserved():

    report = {
        "status": (
            "COMPLETED_WITH_ERRORS"
        ),
        "updated_at": None,
        "open_trades_found": 2,
        "processed": 1,
        "failed": 1,
        "open_trades_after": 2,
        "closed_trades_after": 0,
        "results": [],
    }

    monitor, _, _ = (
        make_monitor(
            report=report
        )
    )

    result = (
        monitor.run_once()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        result[
            "failed"
        ]
        == 1
    )


# ============================================================
# STATUS
# ============================================================


def test_get_status_before_recovery():

    monitor, _, _ = (
        make_monitor()
    )

    status = (
        monitor.get_status()
    )

    assert (
        status[
            "recovered"
        ]
        is False
    )

    assert (
        status[
            "recovered_trade_count"
        ]
        == 0
    )


def test_get_status_after_recovery():

    monitor, _, _ = (
        make_monitor(
            recovered=[
                {
                    "trade_id": "1"
                }
            ]
        )
    )

    monitor.recover()

    status = (
        monitor.get_status()
    )

    assert (
        status[
            "recovered"
        ]
        is True
    )

    assert (
        status[
            "recovered_trade_count"
        ]
        == 1
    )


def test_get_status_returns_trade_counts():

    monitor, _, _ = (
        make_monitor()
    )

    status = (
        monitor.get_status()
    )

    assert (
        status[
            "open_trades"
        ]
        == 2
    )

    assert (
        status[
            "closed_trades"
        ]
        == 1
    )

    assert (
        status[
            "total_trades"
        ]
        == 3
    )