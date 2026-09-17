"""Pure resolution of Task 9 prediction windows from persisted prediction time."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.contracts.prediction_lifecycle_timing_v1 import POLICY_ID, PredictionLifecycleTimingPolicyV1, PredictionLifecycleWindowV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.market_session.policies import MarketSessionPolicy


def resolve_prediction_lifecycle_window(*, prediction_record: PredictionRecordV1, session_policy: MarketSessionPolicy, timing_policy: PredictionLifecycleTimingPolicyV1 = PredictionLifecycleTimingPolicyV1(), task9_session_state=None, task9_segment=None) -> PredictionLifecycleWindowV1:
    if type(prediction_record) is not PredictionRecordV1 or type(session_policy) is not MarketSessionPolicy or type(timing_policy) is not PredictionLifecycleTimingPolicyV1:
        raise TypeError("prediction timing inputs")
    observed = prediction_record.observed_at
    if observed is None:
        raise ValueError("prediction observed_at is required")
    local = observed.astimezone(ZoneInfo(session_policy.timezone))
    if task9_session_state is None:
        cutoff_time, close_time = session_policy.new_entry_cutoff, session_policy.regular_close
    else:
        from services.contracts.task9_market_session_state_v1 import Task9SegmentSessionStateV1
        if type(task9_session_state) is not Task9SegmentSessionStateV1 or task9_segment is None or task9_session_state.segment.value != str(task9_segment) or task9_session_state.market_date != local.date() or task9_session_state.timezone != "Asia/Kolkata" or task9_session_state.new_entry_cutoff is None:
            raise ValueError("invalid canonical Task9 session state")
        cutoff_time, close_time = task9_session_state.new_entry_cutoff, task9_session_state.session_close_time
    cutoff = datetime.combine(local.date(), cutoff_time, tzinfo=local.tzinfo)
    close = datetime.combine(local.date(), close_time, tzinfo=local.tzinfo)
    if local >= close:
        raise ValueError("prediction lifecycle cannot start at or after session close")
    action = prediction_record.predicted_action
    if action in {"CALL", "PUT"}:
        if local > cutoff:
            raise ValueError("prediction occurs after new-entry cutoff")
        entry = min(local + timedelta(minutes=5), cutoff)
    else:
        entry = local
    validity = min(local + timedelta(minutes=15), close)
    return PredictionLifecycleWindowV1(prediction_id=prediction_record.prediction_id, parent_cycle_id=prediction_record.parent_cycle_id, underlying_symbol=prediction_record.underlying_symbol, exchange=prediction_record.exchange, action=action, window_starts_at=observed, entry_window_ends_at=entry, validity_window_ends_at=validity, policy_id=POLICY_ID, provenance="Authoritative Task 9 prediction lifecycle timing policy created at prediction projection.")
