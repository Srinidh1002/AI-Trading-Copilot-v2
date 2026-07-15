from copy import deepcopy

import pytest

from services.market_session_summary import (
    MarketSessionSummaryEngine,
)


def make_entry(
    *,
    timestamp,
    session_date="2026-07-15",
    decision="NO_TRADE",
    market_decision=None,
    direction="BEARISH",
    strategy="TREND_CONTINUATION",
    confidence=80,
    risk_flags=None,
    market_regime="TRENDING_BEARISH",
    setup_status="NO_SETUP",
    paper_trade_status="SKIPPED",
    paper_trade_opened=False,
    market_session_status="SESSION_VALID",
):
    return {
        "timestamp": timestamp,
        "session_date": session_date,
        "decision": decision,
        "market_decision": (
            market_decision
            if market_decision is not None
            else decision
        ),
        "direction": direction,
        "strategy": strategy,
        "confidence": confidence,
        "risk_flags": (
            list(
                risk_flags
            )
            if risk_flags is not None
            else []
        ),
        "market_regime": market_regime,
        "setup_status": setup_status,
        "paper_trade_status": (
            paper_trade_status
        ),
        "paper_trade_opened": (
            paper_trade_opened
        ),
        "market_session_status": (
            market_session_status
        ),
    }


def test_entries_must_be_list():
    engine = (
        MarketSessionSummaryEngine()
    )

    with pytest.raises(
        ValueError,
        match="entries must be a list",
    ):
        engine.summarize(
            {}
        )


def test_every_entry_must_be_dictionary():
    engine = (
        MarketSessionSummaryEngine()
    )

    with pytest.raises(
        ValueError,
        match=(
            "Every journal entry "
            "must be a dictionary"
        ),
    ):
        engine.summarize(
            [
                "invalid",
            ]
        )


def test_empty_session_summary():
    engine = (
        MarketSessionSummaryEngine()
    )

    result = engine.summarize(
        [],
        session_date="2026-07-15",
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )

    assert (
        result[
            "read_only"
        ]
        is True
    )

    assert (
        result[
            "session_date"
        ]
        == "2026-07-15"
    )

    assert (
        result[
            "cycles_observed"
        ]
        == 0
    )

    assert (
        result[
            "decisions"
        ][
            "dominant"
        ]
        is None
    )


def test_session_date_resolved_from_entry():
    engine = (
        MarketSessionSummaryEngine()
    )

    result = engine.summarize(
        [
            make_entry(
                timestamp=(
                    "2026-07-15T09:15:00+05:30"
                ),
            ),
        ]
    )

    assert (
        result[
            "session_date"
        ]
        == "2026-07-15"
    )


def test_decision_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            decision="NO_TRADE",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            decision="NO_TRADE",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            decision="TRADE_READY",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "decisions"
        ][
            "distribution"
        ]
        == {
            "NO_TRADE": 2,
            "TRADE_READY": 1,
        }
    )

    assert (
        result[
            "decisions"
        ][
            "dominant"
        ]
        == "NO_TRADE"
    )


def test_direction_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            direction="BEARISH",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            direction="BEARISH",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            direction="BULLISH",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "directions"
        ][
            "dominant"
        ]
        == "BEARISH"
    )


def test_regime_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            market_regime=(
                "TRENDING_BEARISH"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            market_regime=(
                "TRENDING_BEARISH"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            market_regime="RANGING",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "regimes"
        ][
            "dominant"
        ]
        == "TRENDING_BEARISH"
    )


def test_strategy_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            strategy=(
                "TREND_CONTINUATION"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            strategy=(
                "TREND_CONTINUATION"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            strategy="BREAKOUT",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "strategies"
        ][
            "dominant"
        ]
        == "TREND_CONTINUATION"
    )


def test_confidence_statistics():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            confidence=80,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            confidence=60,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            confidence=100,
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "confidence"
        ]
        == {
            "observations": 3,
            "average": 80.0,
            "minimum": 60.0,
            "maximum": 100.0,
        }
    )


def test_invalid_confidence_values_ignored():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            confidence=None,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            confidence="80",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            confidence=True,
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "confidence"
        ][
            "observations"
        ]
        == 0
    )


def test_risk_flag_frequency():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            risk_flags=[
                "Weak volume",
                "Conflicting patterns",
            ],
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            risk_flags=[
                "Weak volume",
            ],
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "risk_flags"
        ]
        == {
            "Weak volume": 2,
            "Conflicting patterns": 1,
        }
    )


def test_setup_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            setup_status="NO_SETUP",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            setup_status="NO_SETUP",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            setup_status="SETUP_READY",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "setups"
        ][
            "distribution"
        ]
        == {
            "NO_SETUP": 2,
            "SETUP_READY": 1,
        }
    )


def test_paper_trading_statistics():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            paper_trade_status="SKIPPED",
            paper_trade_opened=False,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            paper_trade_status="OPENED",
            paper_trade_opened=True,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            paper_trade_status="BLOCKED",
            paper_trade_opened=False,
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "paper_trading"
        ][
            "opened"
        ]
        == 1
    )

    assert (
        result[
            "paper_trading"
        ][
            "not_opened"
        ]
        == 2
    )

    assert (
        result[
            "paper_trading"
        ][
            "status_distribution"
        ]
        == {
            "BLOCKED": 1,
            "OPENED": 1,
            "SKIPPED": 1,
        }
    )


def test_decision_transitions():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            decision="NO_TRADE",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            decision="NO_TRADE",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            decision="TRADE_READY",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:18:00+05:30"
            ),
            decision="NO_TRADE",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "decision_transitions"
        ][
            "count"
        ]
        == 2
    )

    assert (
        result[
            "decision_transitions"
        ][
            "distribution"
        ]
        == {
            (
                "NO_TRADE -> "
                "TRADE_READY"
            ): 1,
            (
                "TRADE_READY -> "
                "NO_TRADE"
            ): 1,
        }
    )


def test_trade_ready_timing():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            decision="NO_TRADE",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            decision="TRADE_READY",
        ),
        make_entry(
            timestamp=(
                "2026-07-15T10:05:00+05:30"
            ),
            decision="TRADE_READY",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "trade_ready_timing"
        ][
            "count"
        ]
        == 2
    )

    assert (
        result[
            "trade_ready_timing"
        ][
            "first_timestamp"
        ]
        == "2026-07-15T09:17:00+05:30"
    )

    assert (
        result[
            "trade_ready_timing"
        ][
            "last_timestamp"
        ]
        == "2026-07-15T10:05:00+05:30"
    )


def test_market_decision_can_mark_trade_ready():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            decision="ANALYSIS_COMPLETE",
            market_decision="TRADE_READY",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "trade_ready_timing"
        ][
            "count"
        ]
        == 1
    )


def test_session_timing():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:20:30+05:30"
            ),
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "session_timing"
        ][
            "duration_seconds"
        ]
        == 330.0
    )


def test_invalid_timestamps_ignored():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp="invalid",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "session_timing"
        ]
        == {
            "first_timestamp": None,
            "last_timestamp": None,
            "duration_seconds": None,
        }
    )


def test_unknown_values_counted_but_not_dominant():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            direction=None,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            direction=None,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
            direction="BEARISH",
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "directions"
        ][
            "distribution"
        ][
            "UNKNOWN"
        ]
        == 2
    )

    assert (
        result[
            "directions"
        ][
            "dominant"
        ]
        == "BEARISH"
    )


def test_summary_does_not_mutate_entries():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            risk_flags=[
                "Weak volume",
            ],
        ),
    ]

    original = deepcopy(
        entries
    )

    engine.summarize(
        entries
    )

    assert (
        entries
        == original
    )


def test_summary_result_is_independent():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
        ),
    ]

    first = engine.summarize(
        entries
    )

    first[
        "decisions"
    ][
        "distribution"
    ][
        "NO_TRADE"
    ] = 999

    second = engine.summarize(
        entries
    )

    assert (
        second[
            "decisions"
        ][
            "distribution"
        ][
            "NO_TRADE"
        ]
        == 1
    )


def test_market_session_status_distribution():
    engine = (
        MarketSessionSummaryEngine()
    )

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            market_session_status=(
                "SESSION_VALID"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            market_session_status=(
                "SESSION_VALID"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T15:31:00+05:30"
            ),
            market_session_status=(
                "MARKET_CLOSED"
            ),
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "market_session_statuses"
        ][
            "dominant"
        ]
        == "SESSION_VALID"
    )


def test_direction_confidence_prefers_canonical_field():

    engine = MarketSessionSummaryEngine()

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            confidence=100,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            confidence=100,
        ),
    ]

    entries[0][
        "direction_confidence"
    ] = 60

    entries[1][
        "direction_confidence"
    ] = 80

    result = engine.summarize(
        entries
    )

    assert (
        result["direction_confidence"]
        == {
            "observations": 2,
            "average": 70.0,
            "minimum": 60.0,
            "maximum": 80.0,
        }
    )

    assert (
        result["confidence"]
        == result["direction_confidence"]
    )


def test_direction_confidence_falls_back_to_legacy_confidence():

    engine = MarketSessionSummaryEngine()

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
            confidence=60,
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
            confidence=80,
        ),
    ]

    result = engine.summarize(
        entries
    )

    assert (
        result["direction_confidence"]
        == {
            "observations": 2,
            "average": 70.0,
            "minimum": 60.0,
            "maximum": 80.0,
        }
    )


def test_evidence_strength_statistics():

    engine = MarketSessionSummaryEngine()

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
        ),
    ]

    entries[0][
        "evidence_strength_score"
    ] = 20

    entries[1][
        "evidence_strength_score"
    ] = 50

    entries[2][
        "evidence_strength_score"
    ] = 80

    result = engine.summarize(
        entries
    )

    assert (
        result["evidence_strength"]
        == {
            "observations": 3,
            "average": 50.0,
            "minimum": 20.0,
            "maximum": 80.0,
        }
    )


def test_evidence_strength_label_distribution():

    engine = MarketSessionSummaryEngine()

    entries = [
        make_entry(
            timestamp=(
                "2026-07-15T09:15:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:16:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-15T09:17:00+05:30"
            ),
        ),
    ]

    entries[0][
        "evidence_strength_label"
    ] = "LOW"

    entries[1][
        "evidence_strength_label"
    ] = "MEDIUM"

    entries[2][
        "evidence_strength_label"
    ] = "MEDIUM"

    result = engine.summarize(
        entries
    )

    assert (
        result[
            "evidence_strength_labels"
        ][
            "distribution"
        ]
        == {
            "LOW": 1,
            "MEDIUM": 2,
        }
    )

    assert (
        result[
            "evidence_strength_labels"
        ][
            "dominant"
        ]
        == "MEDIUM"
    )
