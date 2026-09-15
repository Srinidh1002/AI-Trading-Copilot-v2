"""Read-only Task 9 close-drain projection from durable lifecycle facts."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.contracts.prediction_record_v1 import (
    prediction_record_from_dict,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
)


IST = ZoneInfo("Asia/Kolkata")
_ABSTENTION_ACTIONS = {"WAIT", "NO_TRADE"}
_ENTRY_ACTIONS = {"CALL", "PUT"}
_MARKETS = {
    "NIFTY": "NSE",
    "SENSEX": "BSE",
}


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _method(value: object, name: str):
    method = getattr(value, name, None)
    if not callable(method):
        raise TypeError(name)
    return method


def _item(
    prediction,
    *,
    kind: Task9CloseDrainItemKind,
    status: Task9CloseDrainItemStatus,
    reasons: tuple[str, ...] = (),
) -> Task9CloseDrainItemV1:
    return Task9CloseDrainItemV1(
        prediction_id=prediction.prediction_id,
        market=prediction.underlying_symbol,
        kind=kind,
        status=status,
        reason_codes=reasons,
    )


def _matches_session(prediction, market_date: date) -> bool:
    return (
        prediction.completed_at.astimezone(IST).date()
        == market_date
    )


def build_task9_close_drain_items(
    *,
    official_run_id: str,
    market_date: date,
    evaluated_at: datetime,
    prediction_ledger,
    binding_store,
    observation_store,
    outcome_store,
    reconciliation_store,
    trade_persistence_service,
) -> tuple[Task9CloseDrainItemV1, ...]:
    """Project session lifecycle facts without mutating any authority."""

    if (
        type(official_run_id) is not str
        or not official_run_id.strip()
    ):
        raise ValueError("official_run_id")
    run_id = official_run_id.strip()

    if type(market_date) is not date:
        raise TypeError("market_date")

    boundary = _aware(
        evaluated_at,
        "evaluated_at",
    )

    all_records = _method(
        prediction_ledger,
        "all_records",
    )
    by_prediction = _method(
        binding_store,
        "by_prediction",
    )
    recover_window = _method(
        observation_store,
        "recover",
    )
    recover_outcome = _method(
        outcome_store,
        "recover",
    )
    recover_reconciliation = _method(
        reconciliation_store,
        "recover",
    )
    get_trade = _method(
        trade_persistence_service,
        "get",
    )

    projected: list[Task9CloseDrainItemV1] = []

    for raw in all_records():
        prediction = prediction_record_from_dict(raw)

        expected_exchange = _MARKETS.get(
            prediction.underlying_symbol
        )
        if expected_exchange is None:
            raise ValueError(
                "unsupported Task9 prediction market"
            )

        if prediction.exchange != expected_exchange:
            raise ValueError(
                "Task9 prediction market identity"
            )

        if not _matches_session(
            prediction,
            market_date,
        ):
            continue

        # Non-COMPLETED child failures are already terminal child
        # dispositions. They have no successful prediction lifecycle
        # work to drain here.
        if prediction.terminal_status != "COMPLETED":
            continue

        action = prediction.predicted_action

        if action in _ABSTENTION_ACTIONS:
            outcome = recover_outcome(
                prediction.prediction_id
            )

            if outcome is not None:
                if (
                    getattr(outcome, "prediction_id", None)
                    != prediction.prediction_id
                    or getattr(
                        outcome,
                        "underlying_symbol",
                        None,
                    )
                    != prediction.underlying_symbol
                    or getattr(outcome, "exchange", None)
                    != prediction.exchange
                ):
                    projected.append(
                        _item(
                            prediction,
                            kind=Task9CloseDrainItemKind.ABSTENTION,
                            status=Task9CloseDrainItemStatus.BLOCKED,
                            reasons=(
                                "ABSTENTION_OUTCOME_IDENTITY_MISMATCH",
                            ),
                        )
                    )
                else:
                    projected.append(
                        _item(
                            prediction,
                            kind=Task9CloseDrainItemKind.ABSTENTION,
                            status=Task9CloseDrainItemStatus.COMPLETE,
                        )
                    )
                continue

            window = recover_window(
                prediction.prediction_id
            )

            if window is None:
                projected.append(
                    _item(
                        prediction,
                        kind=Task9CloseDrainItemKind.ABSTENTION,
                        status=Task9CloseDrainItemStatus.BLOCKED,
                        reasons=(
                            "ABSTENTION_WINDOW_MISSING",
                        ),
                    )
                )
                continue

            if (
                getattr(
                    window,
                    "prediction_id",
                    prediction.prediction_id,
                )
                != prediction.prediction_id
            ):
                projected.append(
                    _item(
                        prediction,
                        kind=Task9CloseDrainItemKind.ABSTENTION,
                        status=Task9CloseDrainItemStatus.BLOCKED,
                        reasons=(
                            "ABSTENTION_WINDOW_IDENTITY_MISMATCH",
                        ),
                    )
                )
                continue

            validity_end = getattr(
                window,
                "validity_window_ends_at",
                None,
            )
            try:
                validity_end = _aware(
                    validity_end,
                    "validity_window_ends_at",
                )
            except (TypeError, ValueError):
                projected.append(
                    _item(
                        prediction,
                        kind=Task9CloseDrainItemKind.ABSTENTION,
                        status=Task9CloseDrainItemStatus.BLOCKED,
                        reasons=(
                            "ABSTENTION_WINDOW_INVALID",
                        ),
                    )
                )
                continue

            if validity_end > boundary:
                projected.append(
                    _item(
                        prediction,
                        kind=Task9CloseDrainItemKind.ABSTENTION,
                        status=Task9CloseDrainItemStatus.PENDING,
                        reasons=(
                            "ABSTENTION_VALIDITY_PENDING",
                        ),
                    )
                )
            else:
                # The coordinator must run the existing provider-free
                # finalizer before evaluating this projection. If the
                # expired durable window still lacks an outcome, the
                # invariant is blocked rather than silently archived.
                projected.append(
                    _item(
                        prediction,
                        kind=Task9CloseDrainItemKind.ABSTENTION,
                        status=Task9CloseDrainItemStatus.BLOCKED,
                        reasons=(
                            "EXPIRED_ABSTENTION_OUTCOME_MISSING",
                        ),
                    )
                )

            continue

        if action not in _ENTRY_ACTIONS:
            # HOLD/EXIT and unknown lifecycle actions are not valid
            # Task9 certification prediction actions.
            raise ValueError(
                "unsupported Task9 prediction action"
            )

        binding = by_prediction(
            prediction.prediction_id
        )

        # A directional prediction that never entered PAPER has no
        # active PAPER lifecycle to drain. Entry/pending-entry recovery
        # remains owned by its dedicated authority.
        if binding is None:
            continue

        if (
            getattr(binding, "official_run_id", None)
            != run_id
            or getattr(binding, "prediction_id", None)
            != prediction.prediction_id
            or getattr(binding, "market", None)
            != prediction.underlying_symbol
            or getattr(
                binding,
                "underlying_exchange",
                prediction.exchange,
            )
            != prediction.exchange
        ):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "BINDING_IDENTITY_MISMATCH",
                    ),
                )
            )
            continue

        entered_at = getattr(
            binding,
            "entered_at",
            None,
        )
        try:
            entered_at = _aware(
                entered_at,
                "entered_at",
            )
        except (TypeError, ValueError):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "BINDING_TIMESTAMP_INVALID",
                    ),
                )
            )
            continue

        if entered_at.astimezone(IST).date() != market_date:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "BINDING_SESSION_DATE_MISMATCH",
                    ),
                )
            )
            continue

        paper_trade_id = getattr(
            binding,
            "paper_trade_id",
            None,
        )

        try:
            snapshot = get_trade(
                paper_trade_id
            )
        except Exception:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "PAPER_SNAPSHOT_INVALID",
                    ),
                )
            )
            continue

        if snapshot is None:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "PAPER_SNAPSHOT_MISSING",
                    ),
                )
            )
            continue

        position = getattr(
            snapshot,
            "position",
            None,
        )
        lifecycle_state = getattr(
            snapshot,
            "lifecycle_state",
            None,
        )

        if (
            getattr(
                snapshot,
                "paper_trade_id",
                None,
            )
            != paper_trade_id
            or position is None
            or getattr(
                position,
                "position_id",
                None,
            )
            != getattr(
                binding,
                "paper_position_id",
                None,
            )
            or lifecycle_state is None
        ):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "PAPER_SNAPSHOT_IDENTITY_MISMATCH",
                    ),
                )
            )
            continue

        is_terminal = getattr(
            lifecycle_state,
            "is_terminal",
            None,
        )
        if type(is_terminal) is not bool:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "PAPER_LIFECYCLE_INVALID",
                    ),
                )
            )
            continue

        if not is_terminal:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.PENDING,
                    reasons=(
                        "PAPER_POSITION_OPEN",
                    ),
                )
            )
            continue

        outcome = recover_outcome(
            prediction.prediction_id
        )
        if outcome is None:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.PENDING,
                    reasons=(
                        "LIFECYCLE_OUTCOME_MISSING",
                    ),
                )
            )
            continue

        if (
            getattr(outcome, "prediction_id", None)
            != prediction.prediction_id
        ):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "LIFECYCLE_OUTCOME_IDENTITY_MISMATCH",
                    ),
                )
            )
            continue

        reconciliation = recover_reconciliation(
            prediction.prediction_id
        )
        if reconciliation is None:
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.PENDING,
                    reasons=(
                        "RECONCILIATION_MISSING",
                    ),
                )
            )
            continue

        expected_position_id = getattr(
            binding,
            "paper_position_id",
            None,
        )
        expected_outcome_id = getattr(
            outcome,
            "outcome_id",
            None,
        )

        if (
            getattr(
                reconciliation,
                "prediction_id",
                None,
            )
            != prediction.prediction_id
            or getattr(
                reconciliation,
                "underlying_symbol",
                None,
            )
            != prediction.underlying_symbol
            or getattr(
                reconciliation,
                "exchange",
                None,
            )
            != prediction.exchange
            or getattr(
                reconciliation,
                "predicted_action",
                None,
            )
            != action
            or getattr(
                reconciliation,
                "position_id",
                None,
            )
            != expected_position_id
            or getattr(
                reconciliation,
                "lifecycle_outcome_id",
                None,
            )
            != expected_outcome_id
        ):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "RECONCILIATION_IDENTITY_MISMATCH",
                    ),
                )
            )
            continue

        status = getattr(
            reconciliation,
            "status",
            None,
        )

        if status == "BLOCKED":
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.BLOCKED,
                    reasons=(
                        "RECONCILIATION_BLOCKED",
                    ),
                )
            )
            continue

        if (
            status == "RECONCILED"
            and getattr(
                reconciliation,
                "reconciliation_complete",
                None,
            )
            is True
            and getattr(
                reconciliation,
                "identity_matches",
                None,
            )
            is True
        ):
            projected.append(
                _item(
                    prediction,
                    kind=Task9CloseDrainItemKind.PAPER_TRADE,
                    status=Task9CloseDrainItemStatus.COMPLETE,
                )
            )
            continue

        projected.append(
            _item(
                prediction,
                kind=Task9CloseDrainItemKind.PAPER_TRADE,
                status=Task9CloseDrainItemStatus.PENDING,
                reasons=(
                    "RECONCILIATION_PENDING",
                ),
            )
        )

    return tuple(
        sorted(
            projected,
            key=lambda item: (
                item.market,
                item.prediction_id,
                item.kind.value,
            ),
        )
    )
