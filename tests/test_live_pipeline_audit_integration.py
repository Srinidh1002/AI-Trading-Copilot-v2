"""
Integration tests for the decision audit trail inside
the live option decision pipeline.

Verifies that:
- Returned decisions contain a structured audit trail.
- Blocked market sessions are audited.
- No-trade decisions are audited.
- Successful trade authorization is audited.
- Audit events preserve pipeline order.

Read-only.
No orders are placed.
"""

from unittest.mock import (
    MagicMock,
    patch,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def make_market_result(
    decision="TRADE",
    direction="BULLISH",
    atr=100,
):
    return {
        "strategy": {
            "decision": decision,
            "direction": direction,
        },
        "technical": {
            "indicators": {
                "atr": atr,
            },
        },
        "candlestick": {
            "support": 24100,
            "resistance": 24300,
        },
        "chart": {},
    }


def make_contract():
    return {
        "selected": True,
        "symbol": "NIFTY14JUL2624200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "premium": 150.0,
        "bid": 149.5,
        "ask": 150.5,
        "volume": 20000,
        "open_interest": 30000,
        "lot_size": 75,
        "score": 10,
    }


def make_pipeline(
    market_result=None,
):
    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        market_result
        if market_result is not None
        else make_market_result()
    )

    option_chain_builder = MagicMock()

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            make_contract()
        ],
    }

    completed_candle_service = MagicMock()

    return LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_chain_builder,
        completed_candle_service=(
            completed_candle_service
        ),
        holiday_calendar=set(),
    )


def test_no_trade_result_contains_audit_trail():

    pipeline = make_pipeline(
        market_result=make_market_result(
            decision="NO_TRADE",
            direction="NEUTRAL",
        )
    )

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "NO_SETUP",
            "direction": "NEUTRAL",
            "trigger_price": None,
            "reasons": [
                "No valid setup."
            ],
        }

        result = pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    audit = result[
        "audit_trail"
    ]

    assert (
        audit["final_decision"]
        == "NO_TRADE"
    )

    assert (
        audit["event_count"]
        > 0
    )

    assert isinstance(
        audit["events"],
        list,
    )


def test_audit_events_have_sequential_numbers():

    pipeline = make_pipeline(
        market_result=make_market_result(
            decision="NO_TRADE",
            direction="NEUTRAL",
        )
    )

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "NO_SETUP",
            "direction": "NEUTRAL",
            "trigger_price": None,
            "reasons": [],
        }

        result = pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )

    events = result[
        "audit_trail"
    ][
        "events"
    ]

    sequences = [
        event["sequence"]
        for event in events
    ]

    assert sequences == list(
        range(
            1,
            len(events) + 1,
        )
    )


def test_market_analysis_is_recorded():

    pipeline = make_pipeline(
        market_result=make_market_result(
            decision="NO_TRADE",
            direction="NEUTRAL",
        )
    )

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "NO_SETUP",
            "direction": "NEUTRAL",
            "trigger_price": None,
            "reasons": [],
        }

        result = pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )

    stages = {
        event["stage"]
        for event in result[
            "audit_trail"
        ][
            "events"
        ]
    }

    assert (
        "MARKET_ANALYSIS"
        in stages
    )


def test_final_decision_is_last_audit_event():

    pipeline = make_pipeline(
        market_result=make_market_result(
            decision="NO_TRADE",
            direction="NEUTRAL",
        )
    )

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "NO_SETUP",
            "direction": "NEUTRAL",
            "trigger_price": None,
            "reasons": [],
        }

        result = pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )

    latest = result[
        "audit_trail"
    ][
        "events"
    ][
        -1
    ]

    assert (
        latest["stage"]
        == "FINAL_DECISION"
    )

    assert (
        latest["decision"]
        == "NO_TRADE"
    )


@patch(
    "services.live_option_decision_pipeline."
    "select_option_contract"
)
def test_trade_ready_contains_complete_audit(
    mock_selector,
):

    pipeline = make_pipeline()

    mock_selector.return_value = (
        make_contract()
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        capital=None,
    )

    assert (
        result["decision"]
        == "TRADE_READY"
    )

    stages = [
        event["stage"]
        for event in result[
            "audit_trail"
        ][
            "events"
        ]
    ]

    assert (
        "MARKET_ANALYSIS"
        in stages
    )

    assert (
        "OPTION_CHAIN"
        in stages
    )

    assert (
        "CONTRACT_SELECTION"
        in stages
    )

    assert (
        stages[-1]
        == "FINAL_DECISION"
    )


@patch(
    "services.live_option_decision_pipeline."
    "build_trade_plan"
)
@patch(
    "services.live_option_decision_pipeline."
    "select_option_contract"
)
def test_trade_allowed_is_audited(
    mock_selector,
    mock_trade_plan,
):

    pipeline = make_pipeline()

    mock_selector.return_value = (
        make_contract()
    )

    mock_trade_plan.return_value = {
        "allowed": True,
        "decision": "TRADE_ALLOWED",
        "reasons": [],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        capital=10000,
    )

    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )

    audit = result[
        "audit_trail"
    ]

    assert (
        audit["final_decision"]
        == "TRADE_ALLOWED"
    )

    stages = [
        event["stage"]
        for event in audit[
            "events"
        ]
    ]

    assert (
        "TRADE_PLAN"
        in stages
    )

    assert (
        stages[-1]
        == "FINAL_DECISION"
    )


@patch(
    "services.live_option_decision_pipeline."
    "evaluate_market_session"
)
def test_closed_market_is_audited(
    mock_session,
):

    mock_session.return_value = {
        "status": "MARKET_CLOSED",
        "allowed": False,
        "market_open": False,
        "reasons": [
            "Market is closed."
        ],
    }

    pipeline = make_pipeline()

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        enforce_market_session=True,
    )

    assert (
        result["decision"]
        == "MARKET_CLOSED"
    )

    audit = result[
        "audit_trail"
    ]

    assert (
        audit["final_decision"]
        == "MARKET_CLOSED"
    )

    stages = [
        event["stage"]
        for event in audit[
            "events"
        ]
    ]

    assert (
        "MARKET_SESSION"
        in stages
    )

    assert (
        stages[-1]
        == "FINAL_DECISION"
    )