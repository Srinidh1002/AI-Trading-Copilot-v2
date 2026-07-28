from datetime import timedelta

from services.external_context import evaluate_event_risk_context
from tests.test_event_risk_context_evaluator import T, event


def test_holiday_is_session_owned_not_policy_blocked():
    holiday = event(
        event_category="EXCHANGE_HOLIDAY",
        event_name="NSE Holiday",
        scheduled_start=T,
        scheduled_end=T + timedelta(hours=6),
        event_status="ACTIVE",
        severity="LOW",
        affected_exchanges=("NSE",),
        session_override_state="MARKET_CLOSED",
        new_entries_allowed=False,
    )

    result = evaluate_event_risk_context(
        underlying_symbol="NIFTY",
        exchange="NSE",
        events=(holiday,),
        created_at=T,
        result_id="r",
    )

    assert result.context_status == "READY_WITH_WARNINGS"
    assert result.entry_restriction_state == "SESSION_OWNED"

    # Market-session validation owns final holiday enforcement.
    assert result.analysis_allowed is True
    assert result.new_entries_allowed is True

    assert result.active_event_count == 1
    assert result.blocking_event_count == 0
    assert result.blockers == ()

    assert result.warnings == ("EVENT CONTEXT WARNING FOR E",)
    assert result.supporting_evidence == (
        "EXCHANGE_HOLIDAY EVENT IS ACTIVE",
    )