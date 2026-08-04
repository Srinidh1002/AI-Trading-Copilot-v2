from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisAuthority,
    CertifiedLiveAnalysisResultV1,
    CertifiedLiveDataAuthority,
    CertifiedLiveDataResultV1,
    CertifiedLiveOpportunityAuthority,
    CertifiedLiveOpportunityResultV1,
    CertifiedSessionAuthority,
)


IST = ZoneInfo("Asia/Kolkata")
MARKET_TIME = datetime(2026, 1, 8, 10, 0, tzinfo=IST)
RECEIVED_AT = datetime(2026, 1, 8, 10, 0, 1, tzinfo=IST)
REQUESTED_AT = datetime(2026, 1, 8, 10, 0, 2, tzinfo=IST)


def cycle_input():
    policy = PaperOrchestrationPolicyV1(
        orchestration_policy_id="certified-policy-1",
        policy_timestamp=MARKET_TIME,
    )
    session = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
        evaluated_at=RECEIVED_AT,
        id_factory=lambda: "session-nifty-1",
    )
    return build_certified_cycle_input(
        cycle_kind="OPPORTUNITY",
        observation_id="observation-1",
        orchestration_policy=policy,
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
        received_at=RECEIVED_AT,
        cycle_requested_at=REQUESTED_AT,
        session_validation=session,
    )


def data_authority():
    return CertifiedLiveDataAuthority(
        reader=lambda value: {
            "symboltoken": "99926000",
            "market_timestamp": value.market_timestamp,
            "received_at": value.received_at,
            "spot_price": 25000.0,
            "payload": {"source": "READ_ONLY_TEST"},
        }
    )


def test_data_authority_returns_exact_paper_only_result():
    value = data_authority()(cycle_input())

    assert type(value) is CertifiedLiveDataResultV1
    assert value.symboltoken == "99926000"
    assert value.spot_price == 25000.0
    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.broker_order_submission is False


def test_data_authority_rejects_invalid_spot():
    authority = CertifiedLiveDataAuthority(
        reader=lambda value: {
            "symboltoken": "99926000",
            "spot_price": 0,
        }
    )

    with pytest.raises(ValueError, match="spot_price"):
        authority(cycle_input())


def test_session_authority_reuses_exact_cycle_validation():
    cycle = cycle_input()
    data = data_authority()(cycle)

    result = CertifiedSessionAuthority()(cycle, data)

    assert result is cycle.session_validation
    assert result.analysis_allowed is True


def test_session_authority_rejects_timestamp_drift():
    cycle = cycle_input()
    data = CertifiedLiveDataResultV1(
        observation_id=cycle.observation_id,
        underlying_symbol="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
        market_timestamp=REQUESTED_AT,
        received_at=REQUESTED_AT,
        spot_price=25000,
    )

    with pytest.raises(ValueError, match="timestamp"):
        CertifiedSessionAuthority()(cycle, data)


def test_analysis_authority_returns_exact_read_only_result():
    cycle = cycle_input()
    data = data_authority()(cycle)
    session = CertifiedSessionAuthority()(cycle, data)
    authority = CertifiedLiveAnalysisAuthority(
        reader=lambda cycle_input, data_result, *, parent_cycle_id: {
            "analysis": {
                "decision": "BULLISH",
                "timeframes": {"5m": "available"},
            },
            "warnings": ("INFORMATIONAL",),
        }
    )

    result = authority(cycle, data, session, parent_cycle_id="test-parent-cycle")

    assert type(result) is CertifiedLiveAnalysisResultV1
    assert result.analysis["decision"] == "BULLISH"
    assert result.warnings == ("INFORMATIONAL",)
    assert result.broker_order_submission is False


def test_analysis_authority_fails_closed_when_session_blocks():
    cycle = cycle_input()
    data = data_authority()(cycle)
    blocked_session = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME.replace(hour=8),
        evaluated_at=RECEIVED_AT,
        id_factory=lambda: "session-blocked",
    )
    authority = CertifiedLiveAnalysisAuthority(
        reader=lambda cycle_input, data_result, *, parent_cycle_id: {}
    )

    with pytest.raises(RuntimeError, match="not allowed"):
        authority(cycle, data, blocked_session, parent_cycle_id="test-parent-cycle")


@pytest.mark.parametrize(
    ("status", "decision", "blockers"),
    (
        ("READY", "TRADE_READY", ()),
        ("NO_ACTION", "NO_TRADE", ()),
        ("BLOCKED", "MARKET_CLOSED", ("MARKET_CLOSED",)),
        ("CONFLICTING", "CONFLICTING", ("CONFLICTING_SIGNALS",)),
        ("FAILED", "FAILED", ("UPSTREAM_FAILURE",)),
    ),
)
def test_opportunity_authority_normalizes_stage_status(
    status,
    decision,
    blockers,
):
    cycle = cycle_input()
    data = data_authority()(cycle)
    session = CertifiedSessionAuthority()(cycle, data)
    analysis = CertifiedLiveAnalysisAuthority(
        reader=lambda cycle_input, data_result, *, parent_cycle_id: {
            "analysis": {"decision": "BULLISH"}
        }
    )(cycle, data, session, parent_cycle_id="test-parent-cycle")
    authority = CertifiedLiveOpportunityAuthority(
        reader=lambda cycle_input, analysis_result, session_result: {
            "opportunity_status": status,
            "decision": decision,
            "blockers": blockers,
            "evidence": {"source": "READ_ONLY_TEST"},
        }
    )

    result = authority(cycle, analysis, session)

    assert type(result) is CertifiedLiveOpportunityResultV1
    assert result.opportunity_status == status
    assert result.decision == decision
    assert result.broker_order_submission is False


def test_blocked_opportunity_requires_reason():
    with pytest.raises(ValueError, match="needs blockers"):
        CertifiedLiveOpportunityResultV1(
            opportunity_status="BLOCKED",
            decision="MARKET_CLOSED",
            underlying_symbol="NIFTY",
            exchange="NSE",
            market_timestamp=MARKET_TIME,
        )


def test_readers_are_called_once_in_exact_order():
    calls = []
    cycle = cycle_input()

    data = CertifiedLiveDataAuthority(
        reader=lambda value: (
            calls.append("DATA")
            or {
                "symboltoken": "99926000",
                "spot_price": 25000,
            }
        )
    )(cycle)
    session = CertifiedSessionAuthority()(cycle, data)
    calls.append("SESSION")
    analysis = CertifiedLiveAnalysisAuthority(
        reader=lambda cycle_input, data_result, *, parent_cycle_id: (
            calls.append("ANALYSIS")
            or {"analysis": {"decision": "BULLISH"}}
        )
    )(cycle, data, session, parent_cycle_id="test-parent-cycle")
    CertifiedLiveOpportunityAuthority(
        reader=lambda cycle_input, analysis_result, session_result: (
            calls.append("OPPORTUNITY")
            or {
                "opportunity_status": "NO_ACTION",
                "decision": "NO_TRADE",
            }
        )
    )(cycle, analysis, session)

    assert calls == ["DATA", "SESSION", "ANALYSIS", "OPPORTUNITY"]
