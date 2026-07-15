from services.trade_candidate_research import (
    evaluate_trade_candidate,
)


def test_very_close_trade_candidate():

    result = evaluate_trade_candidate(
        strategy={
            "direction": "BULLISH",
            "decision": "NO_TRADE",
            "direction_confidence": 80,
            "evidence_strength_score": 80,
            "risk_flags": [
                "Conflicting timeframe signals"
            ],
        },
        setup_trigger={
            "formation_status": "NEAR_TRIGGER",
            "setup_maturity_score": 100,
        },
        timeframe={
            "alignment": "CONFLICTED",
        },
    )

    assert (
        result["trade_candidate_score"]
        == 85
    )

    assert (
        result["candidate_label"]
        == "CLOSE"
    )

    assert (
        result["trade_authorized"]
        is False
    )

    assert (
        "Full timeframe alignment"
        in result["missing_conditions"]
    )

    assert (
        "Resolve risk flags"
        in result["missing_conditions"]
    )


def test_authorized_trade_remains_identified():

    result = evaluate_trade_candidate(
        strategy={
            "direction": "BULLISH",
            "decision": "TRADE",
            "direction_confidence": 90,
            "evidence_strength_score": 90,
            "risk_flags": [],
        },
        setup_trigger={
            "formation_status": "TRIGGERED",
            "setup_maturity_score": 100,
        },
        timeframe={
            "alignment": "FULL",
        },
    )

    assert (
        result["trade_candidate_score"]
        == 100
    )

    assert (
        result["candidate_label"]
        == "AUTHORIZED"
    )

    assert (
        result["trade_authorized"]
        is True
    )


def test_weak_candidate():

    result = evaluate_trade_candidate(
        strategy={
            "direction": "NEUTRAL",
            "decision": "NO_TRADE",
            "direction_confidence": 20,
            "evidence_strength_score": 25,
            "risk_flags": [],
        },
        setup_trigger={
            "formation_status": "NO_SETUP",
            "setup_maturity_score": 0,
        },
        timeframe={
            "alignment": "CONFLICTED",
        },
    )

    assert (
        result["candidate_label"]
        == "WEAK"
    )

    assert (
        result["trade_authorized"]
        is False
    )


def test_developing_candidate():

    result = evaluate_trade_candidate(
        strategy={
            "direction": "BEARISH",
            "decision": "NO_TRADE",
            "direction_confidence": 70,
            "evidence_strength_score": 70,
            "risk_flags": [],
        },
        setup_trigger={
            "formation_status": "DEVELOPING",
            "setup_maturity_score": 60,
        },
        timeframe={
            "alignment": "CONFLICTED",
        },
    )

    assert (
        result["trade_candidate_score"]
        == 70
    )

    assert (
        result["candidate_label"]
        == "DEVELOPING"
    )
