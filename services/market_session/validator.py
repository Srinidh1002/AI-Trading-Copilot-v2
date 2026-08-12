from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.observability import (
    AuditContext,
    AuditEmitter,
    create_audit_event,
)

from .calendar import EmptyTradingCalendar
from .identity import normalize_market_identity
from .policies import (
    BSE_SENSEX_POLICY,
    NSE_NIFTY_POLICY,
    MarketSessionPolicy,
)


IST = ZoneInfo("Asia/Kolkata")

_ALLOWED_VALIDATION_MODES = {
    "LENIENT_ANALYSIS",
    "STRICT_EXECUTION",
}


def _aware_datetime(
    value: object,
    *,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be a timezone-aware datetime."
        )

    return value.astimezone(IST)


def _validation_mode(
    value: object,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "validation_mode must be a supported string."
        )

    normalized = value.strip().upper()

    if normalized not in _ALLOWED_VALIDATION_MODES:
        raise ValueError(
            "validation_mode must be LENIENT_ANALYSIS "
            "or STRICT_EXECUTION."
        )

    return normalized


def _default_policy(
    *,
    exchange: str,
) -> MarketSessionPolicy:
    if exchange == "NSE":
        return NSE_NIFTY_POLICY

    if exchange == "BSE":
        return BSE_SENSEX_POLICY

    return NSE_NIFTY_POLICY


def validate_session_timestamp(
    *,
    symbol,
    exchange,
    market_timestamp,
    evaluated_at,
    calendar=None,
    policy=None,
    validation_mode="LENIENT_ANALYSIS",
    id_factory=None,
    audit_emitter=None,
    audit_context: AuditContext | None = None,
):
    exchange_text = str(exchange).strip().upper()
    symbol_text = str(symbol).strip().upper()
    mode = _validation_mode(validation_mode)

    market_time = _aware_datetime(
        market_timestamp,
        name="market_timestamp",
    )
    evaluation_time = _aware_datetime(
        evaluated_at,
        name="evaluated_at",
    )

    selected_policy = (
        policy
        if policy is not None
        else _default_policy(
            exchange=exchange_text,
        )
    )

    if not isinstance(
        selected_policy,
        MarketSessionPolicy,
    ):
        raise TypeError(
            "policy must be MarketSessionPolicy."
        )

    emitter = audit_emitter or AuditEmitter()

    emitter.emit(
        create_audit_event(
            "SESSION_VALIDATION_STARTED",
            component="market_session",
            operation="validate",
            outcome="STARTED",
            context=audit_context,
            symbol=symbol_text,
            exchange=exchange_text,
        )
    )

    trading_calendar = (
        calendar
        if calendar is not None
        else EmptyTradingCalendar()
    )

    blockers: list[str] = []
    warnings: list[str] = []

    identity = normalize_market_identity(
        symbol_text,
        exchange_text,
    )

    age_seconds = (
        evaluation_time
        - market_time
    ).total_seconds()

    stale = (
        age_seconds
        > selected_policy.max_snapshot_age_seconds
    )

    future_timestamp = (
        age_seconds
        < -selected_policy.max_future_skew_seconds
    )

    trading_day = market_time.date()

    holiday = trading_calendar.holiday_for(
        exchange_text,
        trading_day,
    )

    special_session = (
        trading_calendar.special_session_for(
            exchange_text,
            trading_day,
        )
    )

    session_state = "CLOSED"
    session_phase = "CLOSED_ALL_DAY"
    trading_day_status = "TRADING_DAY"
    session_allows_analysis = False
    regular_new_entry_window_open = False

    if identity is None:
        blockers.append(
            "Unsupported symbol/exchange identity."
        )
        trading_day_status = "UNKNOWN"
        session_state = "UNKNOWN"
        session_phase = "UNKNOWN"

    elif trading_day.weekday() > 4:
        blockers.append(
            "Weekend market closure."
        )
        trading_day_status = "WEEKEND"
        session_state = "WEEKEND"

    elif (
        holiday is not None
        and holiday.full_day
        and special_session is None
    ):
        blockers.append(
            f"Exchange holiday: {holiday.name}"
        )
        trading_day_status = "HOLIDAY"
        session_state = "HOLIDAY"

    elif special_session is not None:
        trading_day_status = "SPECIAL_TRADING_DAY"
        session_state = "SPECIAL"
        session_phase = "SPECIAL_TRADING"
        session_allows_analysis = bool(
            special_session.analysis_allowed
        )

        if not session_allows_analysis:
            blockers.append(
                "Special session does not allow analysis."
            )

    else:
        if (
            getattr(
                trading_calendar,
                "source",
                "EMPTY",
            )
            == "EMPTY"
        ):
            warnings.append(
                "No exchange holiday calendar was supplied."
            )

        market_clock = (
            market_time.timetz()
            .replace(tzinfo=None)
        )

        if (
            selected_policy.regular_open
            <= market_clock
            <= selected_policy.regular_close
        ):
            session_state = "REGULAR"
            session_phase = "REGULAR_TRADING"
            session_allows_analysis = True
            regular_new_entry_window_open = (
                market_clock
                <= selected_policy.new_entry_cutoff
            )

            if not regular_new_entry_window_open:
                warnings.append(
                    "New PAPER entries are closed "
                    "after the session entry cutoff."
                )

        elif (
            selected_policy.pre_open_start
            <= market_clock
            < selected_policy.regular_open
        ):
            session_state = "PRE_OPEN"

            if (
                market_clock
                < selected_policy.pre_open_order_entry_end
            ):
                session_phase = (
                    "PRE_OPEN_ORDER_ENTRY"
                )
            elif (
                market_clock
                < selected_policy.pre_open_matching_end
            ):
                session_phase = "PRE_OPEN_MATCHING"
            else:
                session_phase = "PRE_OPEN_BUFFER"

            blockers.append(
                "Market is not in regular trading session."
            )

        elif market_clock > selected_policy.regular_close:
            session_state = "POST_CLOSE"
            session_phase = "AFTER_MARKET"
            blockers.append(
                "Market is closed for actionable trading."
            )

        else:
            session_phase = "BEFORE_PRE_OPEN"
            blockers.append(
                "Market is closed before pre-open."
            )

    if stale:
        blockers.append(
            "Market timestamp is stale."
        )

    if future_timestamp:
        blockers.append(
            "Market timestamp exceeds allowed future skew."
        )

    calendar_trusted = bool(
        getattr(
            trading_calendar,
            "trusted",
            False,
        )
    )

    if (
        mode == "STRICT_EXECUTION"
        and not calendar_trusted
    ):
        blockers.append(
            "Trusted exchange holiday calendar is "
            "required for execution."
        )

    blockers_tuple = tuple(
        sorted(
            set(blockers)
        )
    )

    warnings_tuple = tuple(
        sorted(
            set(warnings)
        )
    )

    analysis_allowed = (
        session_allows_analysis
        and not stale
        and not future_timestamp
        and not blockers_tuple
    )

    paper_execution_allowed = (
        analysis_allowed
        and (
            mode != "STRICT_EXECUTION"
            or calendar_trusted
        )
        and (
            session_state != "REGULAR"
            or regular_new_entry_window_open
        )
    )

    validation_identifier = (
        id_factory
        if id_factory is not None
        else lambda: str(uuid4())
    )()

    result = MarketSessionValidationV1(
        validation_id=validation_identifier,
        evaluated_at=evaluation_time,
        market_timestamp=market_time,
        symbol=(
            identity.canonical_symbol
            if identity is not None
            else symbol_text
        ),
        exchange=exchange_text,
        timezone="Asia/Kolkata",
        trading_date=trading_day,
        session_state=session_state,
        session_phase=session_phase,
        trading_day_status=trading_day_status,
        is_trading_day=(
            trading_day_status
            in {
                "TRADING_DAY",
                "SPECIAL_TRADING_DAY",
            }
        ),
        regular_session_open=(
            session_state == "REGULAR"
        ),
        analysis_allowed=analysis_allowed,
        paper_preparation_allowed=analysis_allowed,
        paper_execution_allowed=(
            paper_execution_allowed
        ),
        timestamp_age_seconds=age_seconds,
        stale=stale,
        future_timestamp=future_timestamp,
        holiday_name=(
            holiday.name
            if holiday is not None
            else None
        ),
        special_session=(
            special_session is not None
        ),
        special_session_name=(
            special_session.name
            if special_session is not None
            else None
        ),
        blockers=blockers_tuple,
        warnings=warnings_tuple,
        metadata={
            "calendar_source": getattr(
                trading_calendar,
                "source",
                "CUSTOM",
            ),
            "validation_mode": mode,
            "new_entry_cutoff": (
                selected_policy
                .new_entry_cutoff
                .strftime("%H:%M")
            ),
            "regular_close": (
                selected_policy
                .regular_close
                .strftime("%H:%M")
            ),
            "regular_new_entry_window_open": (
                regular_new_entry_window_open
            ),
        },
    )

    emitter.emit(
        create_audit_event(
            (
                "SESSION_VALIDATION_COMPLETED"
                if result.analysis_allowed
                else "SESSION_VALIDATION_BLOCKED"
            ),
            component="market_session",
            operation="validate",
            outcome=(
                "SUCCEEDED"
                if result.analysis_allowed
                else "BLOCKED"
            ),
            context=audit_context,
            snapshot_id=None,
            symbol=result.symbol,
            exchange=result.exchange,
            attributes={
                "session_state": result.session_state,
                "session_phase": result.session_phase,
                "trading_day_status": (
                    result.trading_day_status
                ),
                "stale": result.stale,
                "future_timestamp": (
                    result.future_timestamp
                ),
                "validation_mode": mode,
                "calendar_source": (
                    result.metadata[
                        "calendar_source"
                    ]
                ),
                "blocker_count": len(
                    result.blockers
                ),
            },
        )
    )

    return result


def validate_market_session(
    snapshot,
    *,
    evaluated_at=None,
    calendar=None,
    policy=None,
    validation_mode="LENIENT_ANALYSIS",
    id_factory=None,
    clock=None,
    **kwargs,
):
    now = (
        evaluated_at
        if evaluated_at is not None
        else (
            clock()
            if clock is not None
            else snapshot.captured_at
        )
    )

    return validate_session_timestamp(
        symbol=snapshot.symbol,
        exchange=snapshot.exchange,
        market_timestamp=snapshot.market_timestamp,
        evaluated_at=now,
        calendar=calendar,
        policy=policy,
        validation_mode=validation_mode,
        id_factory=id_factory,
        audit_emitter=kwargs.get(
            "audit_emitter"
        ),
        audit_context=kwargs.get(
            "audit_context"
        ),
    )
