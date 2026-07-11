from services.unified_decision_engine import (
    make_final_decision,
)


def valid_strategy(
    direction="BULLISH",
):
    return {
        "strategy": "BREAKOUT",
        "direction": direction,
        "confidence": 85,
        "decision": "TRADE",
        "confirmations": [
            "Strong setup",
        ],
        "risk_flags": [],
    }


def approved_core_risk():
    return {
        "approved": True,
        "decision": "APPROVED",
        "reasons": [],
        "warnings": [],
    }


def approved_options_risk():
    return {
        "approved": True,
        "decision": "APPROVED",
        "reasons": [],
        "warnings": [],
    }


def test_bullish_trade_becomes_buy_call():

    result = make_final_decision(
        strategy=valid_strategy(
            "BULLISH"
        ),
        core_risk=approved_core_risk(),
        options_risk=(
            approved_options_risk()
        ),
    )

    assert result["approved"] is True
    assert result["decision"] == "TRADE"
    assert result["action"] == "BUY_CALL"


def test_bearish_trade_becomes_buy_put():

    result = make_final_decision(
        strategy=valid_strategy(
            "BEARISH"
        ),
        core_risk=approved_core_risk(),
        options_risk=(
            approved_options_risk()
        ),
    )

    assert result["approved"] is True
    assert result["action"] == "BUY_PUT"


def test_core_risk_rejection_blocks_trade():

    core_risk = {
        "approved": False,
        "decision": "REJECTED",
        "reasons": [
            "Daily loss limit reached."
        ],
        "warnings": [],
    }

    result = make_final_decision(
        strategy=valid_strategy(),
        core_risk=core_risk,
        options_risk=(
            approved_options_risk()
        ),
    )

    assert result["approved"] is False
    assert result["decision"] == "NO_TRADE"
    assert result["action"] == "WAIT"


def test_options_risk_rejection_blocks_trade():

    options_risk = {
        "approved": False,
        "decision": "REJECTED",
        "reasons": [
            "Bid-ask spread too wide."
        ],
        "warnings": [],
    }

    result = make_final_decision(
        strategy=valid_strategy(),
        core_risk=approved_core_risk(),
        options_risk=options_risk,
    )

    assert result["approved"] is False
    assert result["action"] == "WAIT"


def test_strategy_no_trade_is_respected():

    strategy = {
        "strategy": "NO_TRADE",
        "direction": "NEUTRAL",
        "confidence": 30,
        "decision": "NO_TRADE",
        "confirmations": [],
        "risk_flags": [],
    }

    result = make_final_decision(
        strategy=strategy,
        core_risk=approved_core_risk(),
    )

    assert result["approved"] is False
    assert result["decision"] == "NO_TRADE"
    assert result["action"] == "WAIT"