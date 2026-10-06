from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.core.premarket_state_builder_v2 import (
    build_premarket_state_v2,
)


NOW = datetime(
    2026,
    9,
    16,
    3,
    45,
    tzinfo=timezone.utc,
)


def previous_payload():
    return {
        "status": "OK",
        "date": "2026-09-15",
        "open": 23000.0,
        "high": 23200.0,
        "low": 22900.0,
        "close": 23150.0,
        "range": 300.0,
        "range_pct": (
            300.0
            / 23000.0
            * 100
        ),
        "body_pct": (
            150.0
            / 23000.0
            * 100
        ),
        "direction": "UP",
        "close_location": (
            (23150.0 - 22900.0)
            / 300.0
        ),
        "day_type": "RANGE_DAY",
        "atr14": 250.0,
    }


def external_payload():
    return {
        "status": "OK",
        "coverage": "13/13",
        "risk": {
            "sentiment": "RISK_ON",
            "confidence": 0.75,
        },
    }


def vix_payload():
    return {
        "status": "OK",
        "vix": 14.2,
        "change_1d_pct": -2.1,
        "percentile_45d": 42.0,
        "regime": "NORMAL",
        "trend": "FALLING",
    }


def fii_payload():
    return {
        "status": "OK",
        "type": "PREVIOUS_SESSION_CASH_FLOW",
        "trade_date": "15-Sep-2026",
        "fii_cash_net": -800.0,
        "dii_cash_net": 1100.0,
        "combined_net": 300.0,
        "bias": "NEUTRAL",
    }


def legacy_event_payload():
    return {
        "status": "HIGH_IMPACT_EVENT_WITHIN_THRESHOLD",
        "threshold_minutes": 10,
        "events": [
            {
                "name": "IN_CPI",
                "in_minutes": 4.0,
                "country": "IN",
            }
        ],
        "block_entries": True,
    }


def test_builds_complete_previous_session_and_gap_context():
    state = build_premarket_state_v2(
        market_symbol="NIFTY",
        generated_at=NOW,
        previous_day_payload=(
            previous_payload()
        ),
        session_open=23200.0,
        external_payload=(
            external_payload()
        ),
        vix_payload=(
            vix_payload()
        ),
        fii_dii_payload=(
            fii_payload()
        ),
        event_payload={},
    )

    assert (
        state.previous_session_status
        == "AVAILABLE"
    )

    assert (
        state.previous_session.close
        == 23150.0
    )

    assert (
        state.previous_session.atr14
        == 250.0
    )

    assert state.gap is not None

    assert (
        state.gap.gap_points
        == 50.0
    )

    assert state.gap.direction == "UP"

    assert state.gap.atr_multiple == 0.2

    assert state.execution_mode == "PAPER"
    assert state.broker_submission is False

    assert (
        state.live_execution_eligible
        is False
    )


def test_previous_day_fields_are_preserved_in_canonical_state():
    state = build_premarket_state_v2(
        market_symbol="SENSEX",
        generated_at=NOW,
        previous_day_payload=(
            previous_payload()
        ),
        session_open=23150.0,
        external_payload=None,
        vix_payload=None,
        fii_dii_payload=None,
        event_payload=None,
    )

    previous = state.previous_session

    assert previous is not None

    assert previous.open == 23000.0
    assert previous.high == 23200.0
    assert previous.low == 22900.0
    assert previous.close == 23150.0

    assert previous.direction == "UP"
    assert previous.day_type == "RANGE_DAY"

    assert (
        previous.close_location
        > 0.8
    )


def test_unavailable_previous_session_does_not_create_gap():
    state = build_premarket_state_v2(
        market_symbol="NIFTY",
        generated_at=NOW,
        previous_day_payload={
            "status": "EVIDENCE_UNAVAILABLE",
            "reason": "NO_PRIOR_SESSION",
        },
        session_open=23200.0,
        external_payload=None,
        vix_payload=None,
        fii_dii_payload=None,
        event_payload=None,
    )

    assert (
        state.previous_session_status
        == "UNAVAILABLE"
    )

    assert state.previous_session is None
    assert state.gap is None


def test_global_vix_and_institutional_context_are_normalized():
    state = build_premarket_state_v2(
        market_symbol="NIFTY",
        generated_at=NOW,
        previous_day_payload=(
            previous_payload()
        ),
        session_open=23150.0,
        external_payload=(
            external_payload()
        ),
        vix_payload=(
            vix_payload()
        ),
        fii_dii_payload=(
            fii_payload()
        ),
        event_payload=None,
    )

    assert (
        state.global_risk.evidence_status
        == "AVAILABLE"
    )

    assert (
        state.global_risk.sentiment
        == "RISK_ON"
    )

    assert (
        state.global_risk.confidence
        == 0.75
    )

    assert (
        state.volatility.evidence_status
        == "AVAILABLE"
    )

    assert state.volatility.vix == 14.2

    assert (
        state.institutional_flow
        .evidence_status
        == "AVAILABLE"
    )

    assert (
        state.institutional_flow
        .fii_cash_net
        == -800.0
    )

    assert (
        state.institutional_flow
        .dii_cash_net
        == 1100.0
    )


def test_legacy_approximate_calendar_cannot_become_canonical_hard_block():
    state = build_premarket_state_v2(
        market_symbol="NIFTY",
        generated_at=NOW,
        previous_day_payload=(
            previous_payload()
        ),
        session_open=23150.0,
        external_payload=None,
        vix_payload=None,
        fii_dii_payload=None,
        event_payload=(
            legacy_event_payload()
        ),
        event_source_authoritative=False,
    )

    event = state.event_risk

    assert (
        event.evidence_status
        == "UNVERIFIED"
    )

    assert (
        event.provider_block_entries
        is True
    )

    assert (
        event.source_authoritative
        is False
    )

    assert (
        event.hard_block_eligible
        is False
    )


def test_future_authoritative_event_source_can_be_hard_block_eligible():
    state = build_premarket_state_v2(
        market_symbol="NIFTY",
        generated_at=NOW,
        previous_day_payload=(
            previous_payload()
        ),
        session_open=23150.0,
        external_payload=None,
        vix_payload=None,
        fii_dii_payload=None,
        event_payload=(
            legacy_event_payload()
        ),
        event_source_authoritative=True,
    )

    event = state.event_risk

    assert (
        event.evidence_status
        == "AVAILABLE"
    )

    assert (
        event.source_authoritative
        is True
    )

    assert (
        event.hard_block_eligible
        is True
    )


@pytest.mark.parametrize(
    "market",
    (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    ),
)
def test_all_five_canonical_markets_accept_premarket_state(market):
    state = build_premarket_state_v2(
        market_symbol=market,
        generated_at=NOW,
        previous_day_payload=None,
        session_open=None,
        external_payload=None,
        vix_payload=None,
        fii_dii_payload=None,
        event_payload=None,
    )

    assert state.market_symbol == market
    assert state.execution_mode == "PAPER"

    assert (
        state.live_execution_eligible
        is False
    )


def test_builder_requires_timezone_aware_generation_timestamp():
    naive = datetime(
        2026,
        9,
        16,
        9,
        15,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_premarket_state_v2(
            market_symbol="NIFTY",
            generated_at=naive,
            previous_day_payload=None,
            session_open=None,
            external_payload=None,
            vix_payload=None,
            fii_dii_payload=None,
            event_payload=None,
        )


def test_p8b_foundation_has_no_network_or_trading_authority():
    paths = (
        Path(
            "services/contracts/"
            "premarket_intelligence_v2.py"
        ),
        Path(
            "services/core/"
            "premarket_state_builder_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "SmartConnect",
        "fyers_apiv3",
        "requests.get(",
        "yfinance",
        "placeOrder(",
        "place_order",
        "submit_order",
        "BUY_CALL",
        "BUY_PUT",
        "certification_counter",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
