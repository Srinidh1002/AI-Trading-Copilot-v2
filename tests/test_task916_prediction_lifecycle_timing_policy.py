from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_prediction_lifecycle_timing import resolve_prediction_lifecycle_window
from services.certification.task9_live_paper_trade_counting_evaluator import evaluate_task9_live_paper_trade_counting
from services.contracts.prediction_lifecycle_timing_v1 import POLICY_ID, PredictionLifecycleTimingPolicyV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.task9_live_paper_trade_counting_input_v1 import Task9LivePaperTradeCountingInputV1
from services.market_session.policies import MarketSessionPolicy
from services.contracts.task9_market_session_state_v1 import Task9SegmentSessionStateV1


IST = ZoneInfo("Asia/Kolkata")


def prediction(action="CALL", observed_at=None, market="NIFTY", exchange="NSE"):
    observed_at = observed_at or datetime(2026, 8, 10, 10, 0, tzinfo=IST)
    entry_action = action in {"CALL", "PUT"}
    return PredictionRecordV1(prediction_id=f"prediction:{market}:{action}", parent_cycle_id="parent", decision_result_id="decision", child_result_id=f"child:{market}", observation_id=f"observation:{market}", underlying_symbol=market, exchange=exchange, requested_at=observed_at - timedelta(minutes=1), completed_at=observed_at, market_timestamp=observed_at, received_at=observed_at, observed_at=observed_at, start_underlying_price=25000.0 if market == "NIFTY" else 80000.0, terminal_status="COMPLETED", candidate_id="candidate" if entry_action else None, predicted_direction="BULLISH" if action == "CALL" else ("BEARISH" if action == "PUT" else "NEUTRAL"), predicted_action=action, eligibility="ELIGIBLE" if entry_action else "INELIGIBLE", confidence=80.0 if entry_action else 0.0, score=80.0 if entry_action else 0.0, rank_value=80.0 if entry_action else 0.0, eligible_for_comparison=entry_action, outcome_reason="SELECTED" if entry_action else "INELIGIBLE", parent_decision="SELECTED" if entry_action else "NO_TRADE", parent_selected=entry_action)


def resolve(record):
    return resolve_prediction_lifecycle_window(prediction_record=record, session_policy=MarketSessionPolicy(), timing_policy=PredictionLifecycleTimingPolicyV1())


@pytest.mark.parametrize("action", ("CALL", "PUT"))
def test_directional_windows_start_exactly_at_prediction_observed_at(action):
    record = prediction(action)
    window = resolve(record)
    assert window.window_starts_at == record.observed_at
    assert window.entry_window_ends_at == record.observed_at + timedelta(minutes=5)
    assert window.validity_window_ends_at == record.observed_at + timedelta(minutes=15)
    assert window.policy_id == POLICY_ID


def test_wait_and_no_trade_are_zero_duration_entry_with_fifteen_minute_validity():
    record = prediction("WAIT")
    window = resolve(record)
    assert window.entry_window_ends_at == record.observed_at
    assert window.validity_window_ends_at == record.observed_at + timedelta(minutes=15)
    assert record.parent_decision == "NO_TRADE"


def test_no_trade_is_distinct_non_entry_action_and_is_capped_at_session_close():
    record = prediction("NO_TRADE", datetime(2026, 8, 10, 15, 34, tzinfo=IST))
    window = resolve(record)
    assert window.action == "NO_TRADE"
    assert window.window_starts_at == record.observed_at
    assert window.entry_window_ends_at == record.observed_at
    assert window.validity_window_ends_at == datetime(2026, 8, 10, 15, 40, tzinfo=IST)
    assert window.policy_id == POLICY_ID


def test_no_trade_remains_non_countable_without_a_paper_trade():
    record = prediction("NO_TRADE")
    decision = evaluate_task9_live_paper_trade_counting(
        Task9LivePaperTradeCountingInputV1(
            prediction=record, lifecycle_outcome=None, reconciliation=None,
            record_source="LIVE_REAL_TIME", session_status="REAL_TIME_MARKET_SESSION",
            evidence_status="VALID", official_run_id="run", record_run_id="run",
            official_start_at=record.observed_at - timedelta(seconds=1),
            evaluated_at=record.observed_at,
        )
    )
    assert decision.trade_target_countable is False


def test_session_caps_and_inclusive_boundaries():
    record = prediction("CALL", datetime(2026, 8, 10, 15, 18, tzinfo=IST))
    window = resolve(record)
    assert window.entry_window_ends_at == datetime(2026, 8, 10, 15, 20, tzinfo=IST)
    assert window.validity_window_ends_at == datetime(2026, 8, 10, 15, 33, tzinfo=IST)
    assert window.window_starts_at <= record.observed_at <= window.entry_window_ends_at
    assert record.observed_at + timedelta(minutes=2, seconds=1) > window.entry_window_ends_at


def test_close_caps_validity_and_rejects_after_cutoff_or_close():
    wait = resolve(prediction("WAIT", datetime(2026, 8, 10, 15, 34, tzinfo=IST)))
    assert wait.validity_window_ends_at == datetime(2026, 8, 10, 15, 40, tzinfo=IST)
    with pytest.raises(ValueError, match="cutoff"):
        resolve(prediction("CALL", datetime(2026, 8, 10, 15, 20, 1, tzinfo=IST)))
    with pytest.raises(ValueError, match="close"):
        resolve(prediction("WAIT", datetime(2026, 8, 10, 15, 40, tzinfo=IST)))


def test_prediction_record_without_explicit_observed_time_fails_closed():
    record = prediction()
    object.__setattr__(record, "observed_at", None)
    with pytest.raises(ValueError, match="observed_at"):
        resolve(record)

def test_canonical_task9_state_overrides_legacy_close_with_1540_cap():
    observed=datetime(2026,8,10,15,31,tzinfo=IST);state=Task9SegmentSessionStateV1("NFO_OPTIONS",observed.date(),observed,"Asia/Kolkata","ENTRY_RESTRICTED",True,False,True,False,time(9,15),time(15,30),time(15,40),time(15,40),"TRADING_DAY","p","1")
    window=resolve_prediction_lifecycle_window(prediction_record=prediction("WAIT",observed),session_policy=MarketSessionPolicy(),task9_session_state=state,task9_segment="NFO_OPTIONS")
    assert window.validity_window_ends_at==datetime(2026,8,10,15,40,tzinfo=IST)
