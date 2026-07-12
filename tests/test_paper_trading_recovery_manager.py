import pytest

from services.paper_trading_recovery_manager import (
    PaperTradingRecoveryManager,
)


_UNSET = object()


class FakeEngine:

    def __init__(
        self,
        trades=_UNSET,
    ):
        self.trades = (
            []
            if trades is _UNSET
            else trades
        )

        self.calls = 0
        self.last_include_closed = None

    def recover_trades(
        self,
        include_closed=True,
    ):
        self.calls += 1

        self.last_include_closed = (
            include_closed
        )

        return self.trades

class ExplodingEngine:

    def recover_trades(
        self,
        include_closed=True,
    ):
        raise RuntimeError(
            "repository unavailable"
        )


class NoRecoveryEngine:
    pass


class TradeObject:

    def __init__(
        self,
        trade_id,
        status,
    ):
        self.trade_id = trade_id
        self.status = status


class TradeWithAsDict:

    def __init__(
        self,
        trade_id,
        status,
    ):
        self.trade_id = trade_id
        self.status = status

    def as_dict(
        self,
    ):
        return {
            "trade_id": self.trade_id,
            "status": self.status,
        }


def make_trade(
    trade_id="trade-1",
    status="OPEN",
):
    return {
        "trade_id": trade_id,
        "status": status,
    }


# ============================================================
# INITIALIZATION
# ============================================================


def test_requires_engine():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRecoveryManager(
            None
        )


def test_engine_must_expose_recover_trades():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRecoveryManager(
            NoRecoveryEngine()
        )


@pytest.mark.parametrize(
    "value",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_include_closed_must_be_boolean(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRecoveryManager(
            FakeEngine(),
            include_closed=value,
        )


def test_default_include_closed_true():

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine()
        )
    )

    assert (
        manager.include_closed
        is True
    )


# ============================================================
# EMPTY RECOVERY
# ============================================================


def test_empty_recovery():

    engine = FakeEngine(
        []
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "EMPTY"
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["code"]
        == "NO_PERSISTED_TRADES"
    )

    assert (
        result["recovered_count"]
        == 0
    )


def test_recovery_alias():

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine([])
        )
    )

    result = (
        manager.recover_trades()
    )

    assert (
        result["status"]
        == "EMPTY"
    )


# ============================================================
# SUCCESSFUL RECOVERY
# ============================================================


def test_recovers_open_trade():

    engine = FakeEngine(
        [
            make_trade(
                "open-1",
                "OPEN",
            )
        ]
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "RECOVERED"
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["recovered_count"]
        == 1
    )

    assert (
        result["open_count"]
        == 1
    )

    assert (
        result["closed_count"]
        == 0
    )


def test_recovers_closed_trade():

    engine = FakeEngine(
        [
            make_trade(
                "closed-1",
                "CLOSED",
            )
        ]
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result["recovered_count"]
        == 1
    )

    assert (
        result["open_count"]
        == 0
    )

    assert (
        result["closed_count"]
        == 1
    )


def test_recovers_mixed_trades():

    engine = FakeEngine(
        [
            make_trade(
                "open-1",
                "OPEN",
            ),
            make_trade(
                "closed-1",
                "CLOSED",
            ),
            make_trade(
                "open-2",
                "open",
            ),
        ]
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result["recovered_count"]
        == 3
    )

    assert (
        result["open_count"]
        == 2
    )

    assert (
        result["closed_count"]
        == 1
    )


def test_object_trades_supported():

    engine = FakeEngine(
        [
            TradeObject(
                "object-1",
                "OPEN",
            )
        ]
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "RECOVERED"
    )

    assert (
        result["open_count"]
        == 1
    )


def test_as_dict_trade_is_serialized():

    engine = FakeEngine(
        [
            TradeWithAsDict(
                "dict-1",
                "OPEN",
            )
        ]
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    result = manager.recover()

    assert (
        result[
            "recovered_trades"
        ][0][
            "trade_id"
        ]
        == "dict-1"
    )


# ============================================================
# INCLUDE CLOSED
# ============================================================


def test_include_closed_forwarded_true():

    engine = FakeEngine(
        []
    )

    manager = (
        PaperTradingRecoveryManager(
            engine,
            include_closed=True,
        )
    )

    manager.recover()

    assert (
        engine.last_include_closed
        is True
    )


def test_include_closed_forwarded_false():

    engine = FakeEngine(
        []
    )

    manager = (
        PaperTradingRecoveryManager(
            engine,
            include_closed=False,
        )
    )

    manager.recover()

    assert (
        engine.last_include_closed
        is False
    )


def test_engine_called_once():

    engine = FakeEngine(
        []
    )

    manager = (
        PaperTradingRecoveryManager(
            engine
        )
    )

    manager.recover()

    assert (
        engine.calls
        == 1
    )


# ============================================================
# INVALID RECOVERY RESULTS
# ============================================================


def test_none_result_fails_closed():

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                None
            )
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["success"]
        is False
    )

    assert (
        result["failed"]
        is True
    )

    assert (
        result["code"]
        == "INVALID_RECOVERY_RESULT"
    )


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        b"invalid",
        {
            "trade_id": "1",
            "status": "OPEN",
        },
        123,
    ],
)
def test_invalid_recovery_collection_fails(
    value,
):
    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                value
            )
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["code"]
        == "INVALID_RECOVERY_RESULT"
    )


# ============================================================
# INVALID TRADES
# ============================================================


@pytest.mark.parametrize(
    "trade",
    [
        {
            "status": "OPEN",
        },
        {
            "trade_id": "",
            "status": "OPEN",
        },
        {
            "trade_id": None,
            "status": "OPEN",
        },
    ],
)
def test_invalid_trade_id_fails_closed(
    trade,
):
    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                [trade]
            )
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["code"]
        == "INVALID_RECOVERED_TRADE"
    )


@pytest.mark.parametrize(
    "status",
    [
        None,
        "",
        "UNKNOWN",
        "PENDING",
    ],
)
def test_invalid_trade_status_fails_closed(
    status,
):
    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                [
                    make_trade(
                        "trade-1",
                        status,
                    )
                ]
            )
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["code"]
        == "INVALID_RECOVERED_TRADE"
    )


def test_duplicate_trade_id_fails_closed():

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                [
                    make_trade(
                        "duplicate",
                        "OPEN",
                    ),
                    make_trade(
                        "duplicate",
                        "CLOSED",
                    ),
                ]
            )
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["code"]
        == "DUPLICATE_TRADE_ID"
    )

    assert (
        result["recovered_count"]
        == 0
    )


# ============================================================
# ENGINE FAILURE
# ============================================================


def test_engine_exception_fails_closed():

    manager = (
        PaperTradingRecoveryManager(
            ExplodingEngine()
        )
    )

    result = manager.recover()

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["success"]
        is False
    )

    assert (
        result["code"]
        == "RECOVERY_ERROR"
    )

    assert (
        "RuntimeError"
        in result["message"]
    )


# ============================================================
# RESULT STRUCTURE
# ============================================================


def test_success_result_contains_expected_keys():

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                [
                    make_trade()
                ]
            )
        )
    )

    result = manager.recover()

    expected_keys = {
        "status",
        "success",
        "failed",
        "code",
        "message",
        "include_closed",
        "recovered_count",
        "open_count",
        "closed_count",
        "recovered_trades",
        "open_trades",
        "closed_trades",
    }

    assert (
        set(result.keys())
        == expected_keys
    )


def test_failed_result_has_zero_counts():

    manager = (
        PaperTradingRecoveryManager(
            ExplodingEngine()
        )
    )

    result = manager.recover()

    assert (
        result["recovered_count"]
        == 0
    )

    assert (
        result["open_count"]
        == 0
    )

    assert (
        result["closed_count"]
        == 0
    )


def test_dictionary_trade_is_copied():

    original = make_trade(
        "trade-1",
        "OPEN",
    )

    manager = (
        PaperTradingRecoveryManager(
            FakeEngine(
                [original]
            )
        )
    )

    result = manager.recover()

    result[
        "recovered_trades"
    ][0][
        "status"
    ] = "CHANGED"

    assert (
        original["status"]
        == "OPEN"
    )