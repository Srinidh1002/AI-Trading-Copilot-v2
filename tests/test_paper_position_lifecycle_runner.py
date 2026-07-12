import copy

import pytest

from services.paper_position_lifecycle_runner import (
    PaperPositionLifecycleRunner,
)


# ============================================================
# FAKE ENGINE
# ============================================================


class FakePaperTradingEngine:

    def __init__(
        self,
        trades=None,
    ):
        self.trades = (
            copy.deepcopy(
                trades
                or []
            )
        )

        self.update_calls = []

    def get_open_trades(
        self,
    ):
        return copy.deepcopy(
            [
                trade
                for trade in self.trades
                if trade.get(
                    "status"
                ) == "OPEN"
            ]
        )

    def update_price(
        self,
        trade_id,
        current_price,
        updated_at=None,
        auto_close=True,
    ):
        self.update_calls.append(
            {
                "trade_id": trade_id,
                "current_price": (
                    current_price
                ),
                "updated_at": (
                    updated_at
                ),
                "auto_close": (
                    auto_close
                ),
            }
        )

        for trade in self.trades:

            if (
                trade.get(
                    "trade_id"
                )
                == trade_id
            ):

                trade[
                    "current_price"
                ] = current_price

                trade[
                    "updated_at"
                ] = updated_at

                return copy.deepcopy(
                    trade
                )

        raise ValueError(
            "Trade not found."
        )

    def count_open_trades(
        self,
    ):
        return len(
            [
                trade
                for trade in self.trades
                if trade.get(
                    "status"
                ) == "OPEN"
            ]
        )

    def count_closed_trades(
        self,
    ):
        return len(
            [
                trade
                for trade in self.trades
                if trade.get(
                    "status"
                ) == "CLOSED"
            ]
        )


# ============================================================
# HELPERS
# ============================================================


def make_trade(
    trade_id="paper-1",
    status="OPEN",
):
    return {
        "trade_id": trade_id,
        "status": status,
        "symbol": (
            "NIFTY26JUL25000CE"
        ),
        "entry_price": 100.0,
        "stop_loss_price": 80.0,
        "target_price": 140.0,
        "quantity": 75,
    }


def make_runner(
    trades=None,
    price=110.0,
):
    engine = (
        FakePaperTradingEngine(
            trades=trades
        )
    )

    def price_provider(
        trade,
    ):
        return price

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=(
                engine
            ),
            price_provider=(
                price_provider
            ),
        )
    )

    return (
        runner,
        engine,
    )


# ============================================================
# CONSTRUCTOR TESTS
# ============================================================


def test_requires_engine():

    with pytest.raises(
        ValueError
    ):
        PaperPositionLifecycleRunner(
            paper_trading_engine=None,
            price_provider=lambda trade: 100,
        )


def test_requires_price_provider():

    engine = (
        FakePaperTradingEngine()
    )

    with pytest.raises(
        ValueError
    ):
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=None,
        )


def test_price_provider_must_be_callable():

    engine = (
        FakePaperTradingEngine()
    )

    with pytest.raises(
        ValueError
    ):
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=123,
        )


# ============================================================
# PRICE VALIDATION TESTS
# ============================================================


@pytest.mark.parametrize(
    "price, expected",
    [
        (100, 100.0),
        (100.5, 100.5),
        ("125.75", 125.75),
    ],
)
def test_validate_price_accepts_valid_values(
    price,
    expected,
):

    assert (
        PaperPositionLifecycleRunner
        .validate_price(
            price
        )
        == expected
    )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        -100.5,
        None,
        "",
        "abc",
        True,
        False,
        float(
            "nan"
        ),
        float(
            "inf"
        ),
        float(
            "-inf"
        ),
    ],
)
def test_validate_price_rejects_invalid_values(
    price,
):

    with pytest.raises(
        ValueError
    ):
        (
            PaperPositionLifecycleRunner
            .validate_price(
                price
            )
        )


# ============================================================
# PROCESS SINGLE TRADE
# ============================================================


def test_process_trade_updates_price():

    trade = (
        make_trade()
    )

    runner, engine = (
        make_runner(
            trades=[
                trade
            ],
            price=125.5,
        )
    )

    result = (
        runner.process_trade(
            trade,
            updated_at=(
                "2026-07-13T10:00:00+00:00"
            ),
        )
    )

    assert (
        result[
            "status"
        ]
        == "PROCESSED"
    )

    assert (
        result[
            "trade_id"
        ]
        == "paper-1"
    )

    assert (
        result[
            "current_price"
        ]
        == 125.5
    )

    assert (
        len(
            engine.update_calls
        )
        == 1
    )


def test_process_trade_enables_auto_close():

    trade = (
        make_trade()
    )

    runner, engine = (
        make_runner(
            trades=[
                trade
            ]
        )
    )

    runner.process_trade(
        trade
    )

    assert (
        engine.update_calls[
            0
        ][
            "auto_close"
        ]
        is True
    )


def test_process_trade_passes_updated_at():

    trade = (
        make_trade()
    )

    runner, engine = (
        make_runner(
            trades=[
                trade
            ]
        )
    )

    timestamp = (
        "2026-07-13T10:00:00+00:00"
    )

    runner.process_trade(
        trade,
        updated_at=timestamp,
    )

    assert (
        engine.update_calls[
            0
        ][
            "updated_at"
        ]
        == timestamp
    )


def test_process_trade_rejects_missing_trade_id():

    runner, _ = (
        make_runner()
    )

    with pytest.raises(
        ValueError
    ):
        runner.process_trade(
            {
                "status": "OPEN"
            }
        )


def test_process_trade_rejects_invalid_trade():

    runner, _ = (
        make_runner()
    )

    with pytest.raises(
        ValueError
    ):
        runner.process_trade(
            "invalid"
        )


# ============================================================
# RUN TESTS
# ============================================================


def test_run_with_no_open_trades():

    runner, _ = (
        make_runner(
            trades=[]
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )

    assert (
        result[
            "open_trades_found"
        ]
        == 0
    )

    assert (
        result[
            "processed"
        ]
        == 0
    )

    assert (
        result[
            "failed"
        ]
        == 0
    )

    assert (
        result[
            "results"
        ]
        == []
    )


def test_run_processes_one_open_trade():

    runner, engine = (
        make_runner(
            trades=[
                make_trade()
            ],
            price=120.0,
        )
    )

    result = (
        runner.run(
            updated_at=(
                "2026-07-13T10:00:00+00:00"
            )
        )
    )

    assert (
        result[
            "open_trades_found"
        ]
        == 1
    )

    assert (
        result[
            "processed"
        ]
        == 1
    )

    assert (
        result[
            "failed"
        ]
        == 0
    )

    assert (
        len(
            engine.update_calls
        )
        == 1
    )


def test_run_processes_multiple_open_trades():

    trades = [
        make_trade(
            "paper-1"
        ),
        make_trade(
            "paper-2"
        ),
        make_trade(
            "paper-3"
        ),
    ]

    runner, engine = (
        make_runner(
            trades=trades,
            price=115.0,
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "processed"
        ]
        == 3
    )

    assert (
        result[
            "failed"
        ]
        == 0
    )

    assert (
        len(
            engine.update_calls
        )
        == 3
    )


def test_run_ignores_closed_trades():

    trades = [
        make_trade(
            "paper-open",
            status="OPEN",
        ),
        make_trade(
            "paper-closed",
            status="CLOSED",
        ),
    ]

    runner, engine = (
        make_runner(
            trades=trades
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "open_trades_found"
        ]
        == 1
    )

    assert (
        len(
            engine.update_calls
        )
        == 1
    )

    assert (
        engine.update_calls[
            0
        ][
            "trade_id"
        ]
        == "paper-open"
    )


# ============================================================
# FAILURE ISOLATION
# ============================================================


def test_price_provider_failure_is_isolated():

    trades = [
        make_trade(
            "paper-1"
        ),
        make_trade(
            "paper-2"
        ),
    ]

    engine = (
        FakePaperTradingEngine(
            trades
        )
    )

    def price_provider(
        trade,
    ):
        if (
            trade[
                "trade_id"
            ]
            == "paper-1"
        ):
            raise RuntimeError(
                "Price unavailable"
            )

        return 120.0

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=price_provider,
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        result[
            "processed"
        ]
        == 1
    )

    assert (
        result[
            "failed"
        ]
        == 1
    )

    assert (
        len(
            result[
                "results"
            ]
        )
        == 2
    )


def test_invalid_price_is_isolated():

    trades = [
        make_trade(
            "paper-1"
        ),
        make_trade(
            "paper-2"
        ),
    ]

    engine = (
        FakePaperTradingEngine(
            trades
        )
    )

    def price_provider(
        trade,
    ):
        if (
            trade[
                "trade_id"
            ]
            == "paper-1"
        ):
            return -100

        return 120

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=price_provider,
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "processed"
        ]
        == 1
    )

    assert (
        result[
            "failed"
        ]
        == 1
    )


def test_engine_update_failure_is_isolated():

    class FailingEngine(
        FakePaperTradingEngine
    ):

        def update_price(
            self,
            trade_id,
            current_price,
            updated_at=None,
            auto_close=True,
        ):
            if (
                trade_id
                == "paper-1"
            ):
                raise RuntimeError(
                    "Update failed"
                )

            return super().update_price(
                trade_id=trade_id,
                current_price=current_price,
                updated_at=updated_at,
                auto_close=auto_close,
            )

    engine = (
        FailingEngine(
            [
                make_trade(
                    "paper-1"
                ),
                make_trade(
                    "paper-2"
                ),
            ]
        )
    )

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=(
                lambda trade: 120
            ),
        )
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "processed"
        ]
        == 1
    )

    assert (
        result[
            "failed"
        ]
        == 1
    )


# ============================================================
# REPORT TESTS
# ============================================================


def test_run_returns_timestamp():

    runner, _ = (
        make_runner()
    )

    result = (
        runner.run()
    )

    assert (
        result[
            "updated_at"
        ]
        is not None
    )


def test_run_uses_provided_timestamp():

    runner, _ = (
        make_runner()
    )

    timestamp = (
        "2026-07-13T10:00:00+00:00"
    )

    result = (
        runner.run(
            updated_at=timestamp
        )
    )

    assert (
        result[
            "updated_at"
        ]
        == timestamp
    )


def test_run_once_is_alias():

    runner, _ = (
        make_runner(
            trades=[
                make_trade()
            ]
        )
    )

    result = (
        runner.run_once()
    )

    assert (
        result[
            "processed"
        ]
        == 1
    )


def test_results_are_structured():

    runner, _ = (
        make_runner(
            trades=[
                make_trade()
            ]
        )
    )

    result = (
        runner.run()
    )

    item = (
        result[
            "results"
        ][0]
    )

    assert (
        "trade_id"
        in item
    )

    assert (
        "status"
        in item
    )

    assert (
        "current_price"
        in item
    )

    assert (
        "trade"
        in item
    )

    assert (
        "error"
        in item
    )


# ============================================================
# INPUT IMMUTABILITY
# ============================================================


def test_price_provider_receives_copy():

    trade = (
        make_trade()
    )

    original = (
        copy.deepcopy(
            trade
        )
    )

    engine = (
        FakePaperTradingEngine(
            [
                trade
            ]
        )
    )

    def mutating_provider(
        provider_trade,
    ):
        provider_trade[
            "trade_id"
        ] = "MUTATED"

        return 120

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=(
                mutating_provider
            ),
        )
    )

    runner.process_trade(
        trade
    )

    assert (
        trade
        == original
    )


# ============================================================
# INVALID ENGINE RESPONSE
# ============================================================


def test_run_rejects_non_list_open_trades():

    class InvalidEngine(
        FakePaperTradingEngine
    ):

        def get_open_trades(
            self,
        ):
            return {
                "invalid": True
            }

    engine = (
        InvalidEngine()
    )

    runner = (
        PaperPositionLifecycleRunner(
            paper_trading_engine=engine,
            price_provider=(
                lambda trade: 100
            ),
        )
    )

    with pytest.raises(
        ValueError
    ):
        runner.run()