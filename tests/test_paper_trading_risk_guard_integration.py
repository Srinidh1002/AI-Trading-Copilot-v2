from services.paper_trading_orchestrator import (
    PaperTradingOrchestrator,
)
from services.paper_trading_risk_guard import (
    PaperTradingRiskGuard,
)


class FakeEngine:

    def __init__(
        self,
        trades=None,
    ):
        self.trades = list(
            trades or []
        )
        self.open_calls = 0

    def get_all_trades(
        self,
    ):
        return list(
            self.trades
        )

    def open_trade(
        self,
        **kwargs,
    ):
        self.open_calls += 1

        return {
            "trade_id": (
                kwargs.get("trade_id")
                or "paper-1"
            ),
            "status": "OPEN",
            "underlying": kwargs["underlying"],
            "symboltoken": kwargs["symboltoken"],
            "metadata": kwargs["metadata"],
        }


class ExplodingHistoryEngine(
    FakeEngine
):

    def get_all_trades(
        self,
    ):
        raise RuntimeError(
            "history unavailable"
        )


class ExplodingRiskGuard:

    def evaluate(
        self,
        candidate,
        trades,
    ):
        raise RuntimeError(
            "guard failed"
        )


class InvalidRiskGuard:

    def evaluate(
        self,
        candidate,
        trades,
    ):
        return None


def allowed_pipeline(
    symbol="NIFTY_TEST_CE",
):
    return {
        "decision": "TRADE_ALLOWED",
        "selected_contract": {
            "option_symbol": symbol,
        },
    }


def process(
    orchestrator,
    *,
    pipeline_result=None,
    source_decision_id="decision-1",
):
    return orchestrator.process_decision(
        (
            pipeline_result
            or allowed_pipeline()
        ),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="999",
        source_decision_id=(
            source_decision_id
        ),
    )


def make_guard(
    **kwargs,
):
    defaults = {
        "max_open_positions": 2,
        "max_trades_per_day": 5,
        "max_daily_realized_loss": 500.0,
    }

    defaults.update(
        kwargs
    )

    return PaperTradingRiskGuard(
        **defaults
    )


def test_no_risk_guard_preserves_legacy_behavior():

    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine
        )
    )

    result = process(
        orchestrator
    )

    assert result["status"] == "OPENED"
    assert result["risk_guard"] is None
    assert engine.open_calls == 1


def test_allowed_risk_guard_opens_trade():

    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=make_guard(),
        )
    )

    result = process(
        orchestrator
    )

    assert result["status"] == "OPENED"

    assert (
        result["risk_guard"]["allowed"]
        is True
    )

    assert engine.open_calls == 1


def test_kill_switch_blocks_open_trade():

    engine = FakeEngine()

    guard = make_guard(
        kill_switch=True
    )

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=guard,
        )
    )

    result = process(
        orchestrator
    )

    assert result["status"] == "SKIPPED"

    assert (
        result["reason"]
        == "RISK_GUARD_BLOCKED"
    )

    assert (
        result["risk_guard"]["code"]
        == "KILL_SWITCH_ACTIVE"
    )

    assert engine.open_calls == 0


def test_open_position_limit_blocks():

    engine = FakeEngine(
        trades=[
            {
                "trade_id": "existing",
                "status": "OPEN",
                "underlying": "BANKNIFTY",
                "option_symbol": "BANK_TEST",
                "symboltoken": "111",
                "opened_at": (
                    "2026-07-12T09:00:00+00:00"
                ),
            }
        ]
    )

    guard = make_guard(
        max_open_positions=1
    )

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=guard,
        )
    )

    result = process(
        orchestrator
    )

    assert (
        result["risk_guard"]["code"]
        == "MAX_OPEN_POSITIONS_REACHED"
    )

    assert engine.open_calls == 0


def test_duplicate_underlying_blocks():

    engine = FakeEngine(
        trades=[
            {
                "trade_id": "existing",
                "status": "OPEN",
                "underlying": "NIFTY",
                "option_symbol": "OTHER",
                "symboltoken": "111",
                "opened_at": (
                    "2026-07-12T09:00:00+00:00"
                ),
            }
        ]
    )

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=make_guard(),
        )
    )

    result = process(
        orchestrator
    )

    assert (
        result["risk_guard"]["code"]
        == "DUPLICATE_OPEN_POSITION"
    )

    assert engine.open_calls == 0


def test_trade_history_failure_blocks_closed():

    engine = (
        ExplodingHistoryEngine()
    )

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=make_guard(),
        )
    )

    result = process(
        orchestrator
    )

    assert result["status"] == "SKIPPED"

    assert (
        result["risk_guard"]["code"]
        == "TRADE_HISTORY_UNAVAILABLE"
    )

    assert engine.open_calls == 0


def test_risk_guard_exception_blocks_closed():

    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=(
                ExplodingRiskGuard()
            ),
        )
    )

    result = process(
        orchestrator
    )

    assert (
        result["risk_guard"]["code"]
        == "RISK_GUARD_ERROR"
    )

    assert engine.open_calls == 0


def test_invalid_risk_guard_result_blocks_closed():

    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=(
                InvalidRiskGuard()
            ),
        )
    )

    result = process(
        orchestrator
    )

    assert (
        result["risk_guard"]["code"]
        == "INVALID_RISK_GUARD_RESULT"
    )

    assert engine.open_calls == 0


def test_risk_result_added_to_trade_metadata():

    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=make_guard(),
        )
    )

    result = process(
        orchestrator
    )

    assert (
        result[
            "trade"
        ][
            "metadata"
        ][
            "risk_guard"
        ][
            "allowed"
        ]
        is True
    )


def test_non_trade_decision_does_not_call_guard():

    class TrackingGuard:

        def __init__(
            self,
        ):
            self.calls = 0

        def evaluate(
            self,
            candidate,
            trades,
        ):
            self.calls += 1

            return {
                "allowed": True,
                "code": "ALLOWED",
                "message": "ok",
                "metrics": {},
            }

    guard = TrackingGuard()
    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=guard,
        )
    )

    result = process(
        orchestrator,
        pipeline_result={
            "decision": "NO_TRADE",
        },
    )

    assert (
        result["reason"]
        == "DECISION_NOT_TRADE_ALLOWED"
    )

    assert guard.calls == 0


def test_duplicate_source_decision_checked_before_guard():

    class TrackingGuard:

        def __init__(
            self,
        ):
            self.calls = 0

        def evaluate(
            self,
            candidate,
            trades,
        ):
            self.calls += 1

            return {
                "allowed": True,
                "code": "ALLOWED",
                "message": "ok",
                "metrics": {},
            }

    guard = TrackingGuard()
    engine = FakeEngine()

    orchestrator = (
        PaperTradingOrchestrator(
            engine,
            risk_guard=guard,
        )
    )

    first = process(
        orchestrator
    )

    second = process(
        orchestrator
    )

    assert first["status"] == "OPENED"

    assert (
        second["reason"]
        == "DUPLICATE_SOURCE_DECISION"
    )

    assert guard.calls == 1


def test_invalid_risk_guard_constructor_rejected():

    try:
        PaperTradingOrchestrator(
            FakeEngine(),
            risk_guard=object(),
        )

    except ValueError:
        passed = True

    else:
        passed = False

    assert passed is True