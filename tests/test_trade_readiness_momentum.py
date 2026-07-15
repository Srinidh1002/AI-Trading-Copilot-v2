import pytest

from services.trade_readiness_momentum import (
    TradeReadinessMomentum,
)


def make_entry(
    *,
    decision="NO_TRADE",
    direction="BEARISH",
    confidence=70,
    risk_flags=None,
    setup_status="NO_SETUP",
    timestamp=None,
):
    if risk_flags is None:
        risk_flags = []

    return {
        "decision": decision,
        "direction": direction,
        "confidence": confidence,
        "risk_flags": risk_flags,
        "setup_status": setup_status,
        "timestamp": timestamp,
    }


def make_engine():
    return TradeReadinessMomentum()


def test_none_entries_returns_empty_analysis():
    result = make_engine().analyze(
        None
    )

    assert result["cycles_observed"] == 0
    assert result["momentum"] == "UNAVAILABLE"


def test_invalid_entries_rejected():
    with pytest.raises(
        ValueError,
        match="entries must be a list or tuple",
    ):
        make_engine().analyze(
            {
                "decision": "NO_TRADE",
            }
        )


def test_non_dictionary_entries_ignored():
    result = make_engine().analyze(
        [
            None,
            "bad",
            123,
            make_entry(),
        ]
    )

    assert result["cycles_observed"] == 1


def test_building_momentum_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=60,
                risk_flags=["A", "B"],
                setup_status="NO_SETUP",
            ),
            make_entry(
                confidence=70,
                risk_flags=["A"],
                setup_status="DEVELOPING",
            ),
            make_entry(
                confidence=80,
                risk_flags=[],
                setup_status="CONFIRMED",
            ),
        ]
    )

    assert result["momentum"] == "BUILDING"


def test_deteriorating_momentum_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=90,
                risk_flags=[],
                setup_status="CONFIRMED",
            ),
            make_entry(
                confidence=70,
                risk_flags=["A"],
                setup_status="DEVELOPING",
            ),
            make_entry(
                confidence=50,
                risk_flags=["A", "B"],
                setup_status="NO_SETUP",
            ),
        ]
    )

    assert (
        result["momentum"]
        == "DETERIORATING"
    )


def test_flat_momentum_detected():
    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    result = make_engine().analyze(
        entries
    )

    assert result["momentum"] == "FLAT"


def test_mixed_momentum_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=80
            ),
            make_entry(
                confidence=50
            ),
        ]
    )

    assert result["momentum"] == "MIXED"


def test_single_cycle_momentum_unavailable():
    result = make_engine().analyze(
        [
            make_entry(),
        ]
    )

    assert (
        result["momentum"]
        == "UNAVAILABLE"
    )


def test_readiness_change_calculated():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=50,
                risk_flags=["A", "B"],
                setup_status="NO_SETUP",
            ),
            make_entry(
                confidence=90,
                risk_flags=[],
                setup_status="CONFIRMED",
            ),
        ]
    )

    assert result["readiness"]["change"] > 0


def test_confidence_improving_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=80
            ),
        ]
    )

    assert (
        result["confidence"]["improving"]
        is True
    )


def test_confidence_decline_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=80
            ),
            make_entry(
                confidence=60
            ),
        ]
    )

    assert (
        result["confidence"]["improving"]
        is False
    )


def test_risk_flags_improving_detected():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A", "B", "C"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
        ]
    )

    assert (
        result["risk_flags"]["improving"]
        is True
    )


def test_risk_flags_not_improving_detected():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=[]
            ),
            make_entry(
                risk_flags=["A"]
            ),
        ]
    )

    assert (
        result["risk_flags"]["improving"]
        is False
    )


def test_setup_improving_detected():
    result = make_engine().analyze(
        [
            make_entry(
                setup_status="NO_SETUP"
            ),
            make_entry(
                setup_status="DEVELOPING"
            ),
            make_entry(
                setup_status="CONFIRMED"
            ),
        ]
    )

    assert result["setup"]["improving"] is True


def test_setup_not_improving_detected():
    result = make_engine().analyze(
        [
            make_entry(
                setup_status="CONFIRMED"
            ),
            make_entry(
                setup_status="NO_SETUP"
            ),
        ]
    )

    assert result["setup"]["improving"] is False


def test_direction_stable_detected():
    result = make_engine().analyze(
        [
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
        ]
    )

    assert (
        result[
            "direction_stability"
        ][
            "stable"
        ]
        is True
    )


def test_direction_changes_counted():
    result = make_engine().analyze(
        [
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BULLISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
        ]
    )

    assert (
        result[
            "direction_stability"
        ][
            "changes"
        ]
        == 2
    )


def test_trade_ready_observed():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(
                decision="TRADE_READY"
            ),
        ]
    )

    assert (
        result["trade_ready"]["observed"]
        is True
    )

    assert (
        result["trade_ready"]["first_index"]
        == 1
    )


def test_cycles_before_trade_ready_calculated():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(),
            make_entry(),
            make_entry(
                decision="TRADE_READY"
            ),
        ]
    )

    assert (
        result["trade_ready"]["cycles_before"]
        == 3
    )


def test_trade_ready_not_observed():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(),
        ]
    )

    assert (
        result["trade_ready"]["observed"]
        is False
    )

    assert (
        result["trade_ready"]["first_index"]
        is None
    )


def test_pre_trade_build_up_detected():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=55,
                risk_flags=["A", "B", "C"],
                setup_status="NO_SETUP",
            ),
            make_entry(
                confidence=65,
                risk_flags=["A", "B"],
                setup_status="DEVELOPING",
            ),
            make_entry(
                confidence=78,
                risk_flags=["A"],
                setup_status="PENDING_CONFIRMATION",
            ),
            make_entry(
                decision="TRADE_READY",
                confidence=90,
                risk_flags=[],
                setup_status="CONFIRMED",
            ),
        ]
    )

    assert (
        result[
            "trade_ready"
        ][
            "pre_trade_build_up_detected"
        ]
        is True
    )


def test_immediate_trade_ready_not_build_up():
    result = make_engine().analyze(
        [
            make_entry(
                decision="TRADE_READY",
                confidence=90,
                setup_status="CONFIRMED",
            ),
        ]
    )

    assert (
        result[
            "trade_ready"
        ][
            "pre_trade_build_up_detected"
        ]
        is False
    )


def test_risk_flags_string_supported():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags="RISK"
            ),
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "risk_flag_count"
        ]
        == 1
    )


def test_nested_market_decision_risk_flags_supported():
    entry = make_entry(
        risk_flags=None
    )

    entry.pop(
        "risk_flags"
    )

    entry[
        "market_decision"
    ] = {
        "risk_flags": [
            "A",
            "B",
        ],
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "risk_flag_count"
        ]
        == 2
    )


def test_setup_dictionary_supported():
    entry = make_entry(
        setup_status=None
    )

    entry[
        "setup"
    ] = {
        "status": "CONFIRMED",
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "setup_status"
        ]
        == "CONFIRMED"
    )


def test_strategy_confidence_supported():
    entry = make_entry(
        confidence=None
    )

    entry[
        "strategy"
    ] = {
        "confidence": 88,
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "first"
        ]
        == 88.0
    )


def test_boolean_confidence_ignored():
    result = make_engine().analyze(
        [
            make_entry(
                confidence=True
            ),
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "confidence"
        ]
        is None
    )


def test_readiness_score_bounded():
    result = make_engine().analyze(
        [
            make_entry(
                decision="TRADE_READY",
                confidence=500,
                risk_flags=[],
                setup_status="TRADE_READY",
            ),
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "readiness_score"
        ]
        <= 100
    )


def test_timestamp_preserved_for_trade_ready():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(
                decision="TRADE_READY",
                timestamp="T2",
            ),
        ]
    )

    assert (
        result[
            "trade_ready"
        ][
            "first_timestamp"
        ]
        == "T2"
    )


def test_session_date_preserved():
    result = make_engine().analyze(
        [],
        session_date="2026-07-15",
    )

    assert (
        result["session_date"]
        == "2026-07-15"
    )


def test_result_is_read_only():
    result = make_engine().analyze(
        []
    )

    assert result["read_only"] is True


def test_input_not_modified():
    entries = [
        make_entry(
            confidence=70
        ),
    ]

    original = [
        make_entry(
            confidence=70
        ),
    ]

    make_engine().analyze(
        entries
    )

    assert entries == original


def test_direction_confidence_takes_priority_over_legacy_confidence():

    entry = make_entry(
        confidence=20
    )

    entry[
        "direction_confidence"
    ] = 88

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "confidence"
        ]
        == 88.0
    )


def test_legacy_confidence_fallback_remains_supported():

    entry = make_entry(
        confidence=73
    )

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "cycle_states"
        ][
            0
        ][
            "confidence"
        ]
        == 73.0
    )