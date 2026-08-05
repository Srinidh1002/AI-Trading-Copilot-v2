"""Deterministic CALL/PUT and WAIT/NO_TRADE lifecycle outcomes."""
from __future__ import annotations

from collections import defaultdict

from services.contracts.prediction_lifecycle_outcome_input_v1 import (
    PredictionLifecycleOutcomeInputV1,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)


_TARGET_LEVEL = {"T1": 1, "T2": 2, "T3": 3}


def _movement(value):
    window = value.observation_window
    start = value.prediction.start_underlying_price
    if (
        window.highest_underlying_price is None
        or window.lowest_underlying_price is None
    ):
        return None, None, None
    up = max(
        0.0,
        (window.highest_underlying_price - start) / start * 100.0,
    )
    down = max(
        0.0,
        (start - window.lowest_underlying_price) / start * 100.0,
    )
    return up, down, max(up, down)


def _record(
    *,
    value,
    status,
    outcome,
    highest_target=0,
    terminal_event_type=None,
    terminal_event_at=None,
    terminal_option_premium=None,
    blockers=(),
):
    prediction = value.prediction
    window = value.observation_window
    up, down, absolute = _movement(value)
    return PredictionLifecycleOutcomeRecordV1(
        outcome_id=(
            f"lifecycle-outcome:{prediction.prediction_id}:"
            f"{window.window_id}:{value.policy.policy_version}"
        ),
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        decision_result_id=prediction.decision_result_id,
        window_id=window.window_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        policy_id=value.policy.policy_id,
        policy_version=value.policy.policy_version,
        evaluated_at=value.evaluated_at,
        evaluation_status=status,
        outcome=outcome,
        entry_occurred=window.entry_occurred,
        entry_at=window.entry_at,
        entry_premium=window.entry_premium,
        highest_target_reached=highest_target,
        terminal_event_type=terminal_event_type,
        terminal_event_at=terminal_event_at,
        terminal_option_premium=terminal_option_premium,
        maximum_up_move_percent=up,
        maximum_down_move_percent=down,
        maximum_absolute_move_percent=absolute,
        evidence_observation_ids=tuple(
            item.observation_id for item in window.observations
        ),
        blockers=blockers,
    )


def _target_outcome(level):
    return {1: "T1_HIT", 2: "T2_HIT", 3: "T3_HIT"}[level]


def _premium(items):
    for item in reversed(items):
        if item.option_premium is not None:
            return item.option_premium
    return None


def _directional(value):
    window = value.observation_window
    policy = value.policy

    if policy.any_data_gap_is_unavailable and window.data_gap_count:
        return _record(
            value=value,
            status="DATA_UNAVAILABLE",
            outcome="DATA_UNAVAILABLE",
            terminal_event_type=window.terminal_event_type,
            terminal_event_at=window.terminal_event_at,
            blockers=("OBSERVATION_WINDOW_CONTAINS_DATA_GAP",),
        )

    if not window.entry_occurred:
        invalidated = next(
            (
                item
                for item in window.observations
                if item.event_type == "INVALIDATED"
            ),
            None,
        )
        if invalidated is not None:
            return _record(
                value=value,
                status="RESOLVED",
                outcome="INVALIDATED_BEFORE_ENTRY",
                terminal_event_type="INVALIDATED",
                terminal_event_at=invalidated.observed_at,
                terminal_option_premium=invalidated.option_premium,
            )

        ended = (
            value.evaluated_at >= window.validity_window_ends_at
            or window.session_closed
            or window.expiry_reached
        )
        if ended:
            terminal_type = (
                "EXPIRY"
                if window.expiry_reached
                else "SESSION_CLOSE"
                if window.session_closed
                else "VALIDITY_WINDOW_END"
            )
            terminal_at = (
                window.expiry_reached_at
                or window.session_closed_at
                or window.validity_window_ends_at
            )
            return _record(
                value=value,
                status="RESOLVED",
                outcome="EXPIRED_WITHOUT_ENTRY",
                terminal_event_type=terminal_type,
                terminal_event_at=terminal_at,
            )

        return _record(
            value=value,
            status="UNRESOLVED",
            outcome="UNRESOLVED",
            blockers=("ENTRY_WINDOW_OR_VALIDITY_WINDOW_OPEN",),
        )

    grouped = defaultdict(list)
    for item in window.observations:
        if item.observed_at >= window.entry_at and item.event_type != "NONE":
            grouped[item.observed_at].append(item)

    highest_target = 0
    for observed_at in sorted(grouped):
        group = tuple(
            sorted(grouped[observed_at], key=lambda item: item.sequence_number)
        )
        events = {item.event_type for item in group}
        group_highest = max(
            (_TARGET_LEVEL[event] for event in events if event in _TARGET_LEVEL),
            default=0,
        )

        if (
            "STOP" in events
            and group_highest
            and policy.same_observation_precedence
            in {"STOP_FIRST", "CONSERVATIVE_STOP_FIRST"}
        ):
            if highest_target:
                return _record(
                    value=value,
                    status="RESOLVED",
                    outcome=_target_outcome(highest_target),
                    highest_target=highest_target,
                    terminal_event_type="STOP",
                    terminal_event_at=observed_at,
                    terminal_option_premium=_premium(group),
                )
            return _record(
                value=value,
                status="RESOLVED",
                outcome="STOP_HIT",
                terminal_event_type="STOP",
                terminal_event_at=observed_at,
                terminal_option_premium=_premium(group),
            )

        highest_target = max(highest_target, group_highest)
        if highest_target == 3:
            return _record(
                value=value,
                status="RESOLVED",
                outcome="T3_HIT",
                highest_target=3,
                terminal_event_type="T3",
                terminal_event_at=observed_at,
                terminal_option_premium=_premium(group),
            )

        terminal_event = next(
            (
                event
                for event in (
                    "STOP",
                    "EARLY_EXIT",
                    "INVALIDATED",
                    "SESSION_CLOSE",
                    "EXPIRY",
                )
                if event in events
            ),
            None,
        )
        if terminal_event is None:
            continue

        if highest_target:
            return _record(
                value=value,
                status="RESOLVED",
                outcome=_target_outcome(highest_target),
                highest_target=highest_target,
                terminal_event_type=terminal_event,
                terminal_event_at=observed_at,
                terminal_option_premium=_premium(group),
            )

        terminal_premium = _premium(group)
        if terminal_event == "STOP":
            return _record(
                value=value,
                status="RESOLVED",
                outcome="STOP_HIT",
                terminal_event_type="STOP",
                terminal_event_at=observed_at,
                terminal_option_premium=terminal_premium,
            )
        if terminal_premium is None:
            return _record(
                value=value,
                status="DATA_UNAVAILABLE",
                outcome="DATA_UNAVAILABLE",
                terminal_event_type=terminal_event,
                terminal_event_at=observed_at,
                blockers=("TERMINAL_EVENT_MISSING_OPTION_PREMIUM",),
            )

        outcome = (
            "EARLY_EXIT_PROFIT"
            if terminal_premium > window.entry_premium
            else "EARLY_EXIT_LOSS"
        )
        return _record(
            value=value,
            status="RESOLVED",
            outcome=outcome,
            terminal_event_type=terminal_event,
            terminal_event_at=observed_at,
            terminal_option_premium=terminal_premium,
        )

    return _record(
        value=value,
        status="UNRESOLVED",
        outcome="UNRESOLVED",
        highest_target=highest_target,
        blockers=(
            "TARGET_REACHED_WITHOUT_TERMINAL_EVIDENCE"
            if highest_target
            else "OPEN_POSITION_HAS_NO_TERMINAL_EVIDENCE",
        ),
    )


def _abstention(value):
    window = value.observation_window
    policy = value.policy

    if policy.any_data_gap_is_unavailable and window.data_gap_count:
        return _record(
            value=value,
            status="DATA_UNAVAILABLE",
            outcome="DATA_UNAVAILABLE",
            terminal_event_type=window.terminal_event_type,
            terminal_event_at=window.terminal_event_at,
            blockers=("OBSERVATION_WINDOW_CONTAINS_DATA_GAP",),
        )

    ended = (
        value.evaluated_at >= window.validity_window_ends_at
        or window.session_closed
        or window.expiry_reached
    )
    if not ended:
        return _record(
            value=value,
            status="UNRESOLVED",
            outcome="UNRESOLVED",
            blockers=("WAIT_EVALUATION_WINDOW_OPEN",),
        )

    _, _, maximum_absolute = _movement(value)
    if maximum_absolute is None:
        return _record(
            value=value,
            status="DATA_UNAVAILABLE",
            outcome="DATA_UNAVAILABLE",
            terminal_event_type=window.terminal_event_type,
            terminal_event_at=window.terminal_event_at,
            blockers=("UNDERLYING_EXTREMA_UNAVAILABLE",),
        )

    outcome = (
        "NO_TRADE_MISSED_MOVE"
        if maximum_absolute >= policy.no_trade_move_threshold_percent
        else "NO_TRADE_CORRECT"
    )
    terminal_type = (
        "EXPIRY"
        if window.expiry_reached
        else "SESSION_CLOSE"
        if window.session_closed
        else "VALIDITY_WINDOW_END"
    )
    terminal_at = (
        window.expiry_reached_at
        or window.session_closed_at
        or window.validity_window_ends_at
    )
    return _record(
        value=value,
        status="RESOLVED",
        outcome=outcome,
        terminal_event_type=terminal_type,
        terminal_event_at=terminal_at,
    )


def evaluate_prediction_lifecycle_outcome(value):
    """Evaluate one retained prediction from ordered supplied evidence."""
    if type(value) is not PredictionLifecycleOutcomeInputV1:
        raise TypeError("value")
    if value.prediction.predicted_action in {"CALL", "PUT"}:
        return _directional(value)
    return _abstention(value)
