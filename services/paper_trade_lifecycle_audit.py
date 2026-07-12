"""
Paper-trade lifecycle audit service.

Creates a structured, append-only in-memory history of
paper-trade lifecycle events.

This service is informational only.

It:
- does not place real orders
- does not call broker order APIs
- does not authorize live trades
- does not modify trading decisions
"""

from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)
from math import isfinite


class PaperTradeLifecycleEvent:
    """
    Supported paper-trade lifecycle event names.
    """

    OPENED = "OPENED"
    PRICE_UPDATED = "PRICE_UPDATED"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    TARGET_HIT = "TARGET_HIT"
    CLOSED = "CLOSED"


class PaperTradeLifecycleAudit:
    """
    Maintain an append-only in-memory audit trail for one
    paper trade.

    Every event contains:
    - sequence
    - timestamp
    - trade_id
    - event
    - status
    - price
    - realized_pnl
    - unrealized_pnl
    - reason
    - details

    Returned values are defensive deep copies.
    """

    _ALLOWED_EVENTS = {
        PaperTradeLifecycleEvent.OPENED,
        PaperTradeLifecycleEvent.PRICE_UPDATED,
        PaperTradeLifecycleEvent.STOP_LOSS_HIT,
        PaperTradeLifecycleEvent.TARGET_HIT,
        PaperTradeLifecycleEvent.CLOSED,
    }

    def __init__(
        self,
        trade_id,
        timestamp_factory=None,
    ):
        self.trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        self._timestamp_factory = (
            timestamp_factory
            if timestamp_factory is not None
            else self._utc_timestamp
        )

        if not callable(
            self._timestamp_factory
        ):
            raise TypeError(
                "timestamp_factory must be callable."
            )

        self._events = []

    @staticmethod
    def _utc_timestamp():
        """
        Return the current timezone-aware UTC timestamp.
        """

        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

    @staticmethod
    def _validate_trade_id(
        trade_id,
    ):
        """
        Validate and normalize a paper trade identifier.
        """

        if not isinstance(
            trade_id,
            str,
        ):
            raise ValueError(
                "trade_id must be a non-empty string."
            )

        normalized = (
            trade_id.strip()
        )

        if not normalized:
            raise ValueError(
                "trade_id must be a non-empty string."
            )

        return normalized

    @classmethod
    def _validate_event(
        cls,
        event,
    ):
        """
        Validate and normalize a lifecycle event.
        """

        if not isinstance(
            event,
            str,
        ):
            raise ValueError(
                "event must be a valid lifecycle event."
            )

        normalized = (
            event.strip()
            .upper()
        )

        if (
            normalized
            not in cls._ALLOWED_EVENTS
        ):
            raise ValueError(
                "Unsupported paper-trade lifecycle event: "
                f"{normalized}"
            )

        return normalized

    @staticmethod
    def _normalize_status(
        status,
    ):
        """
        Normalize an optional trade status.
        """

        if status is None:
            return None

        if hasattr(
            status,
            "value",
        ):
            status = (
                status.value
            )

        text = str(
            status
        ).strip()

        if not text:
            return None

        return text.upper()

    @staticmethod
    def _validate_optional_number(
        value,
        field_name,
    ):
        """
        Validate an optional finite numeric value.

        Booleans are rejected because bool is a subclass
        of int in Python.
        """

        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a finite number."
            )

        try:
            numeric = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} must be a finite number."
            ) from exc

        if not isfinite(
            numeric
        ):
            raise ValueError(
                f"{field_name} must be a finite number."
            )

        return numeric

    @classmethod
    def _validate_optional_price(
        cls,
        value,
    ):
        """
        Validate an optional positive finite price.
        """

        numeric = (
            cls._validate_optional_number(
                value,
                "price",
            )
        )

        if numeric is None:
            return None

        if numeric <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        return numeric

    @staticmethod
    def _normalize_reason(
        reason,
    ):
        """
        Normalize an optional human-readable reason.
        """

        if reason is None:
            return None

        text = str(
            reason
        ).strip()

        if not text:
            return None

        return text

    @staticmethod
    def _validate_details(
        details,
    ):
        """
        Validate and defensively copy event details.
        """

        if details is None:
            return {}

        if not isinstance(
            details,
            dict,
        ):
            raise TypeError(
                "details must be a dictionary."
            )

        return deepcopy(
            details
        )

    def record(
        self,
        event,
        status=None,
        price=None,
        realized_pnl=None,
        unrealized_pnl=None,
        reason=None,
        details=None,
        timestamp=None,
    ):
        """
        Append one lifecycle event.

        Parameters
        ----------
        event : str
            Supported lifecycle event.

        status : str, optional
            Paper-trade status.

        price : float, optional
            Relevant option price.

        realized_pnl : float, optional
            Realized paper P&L.

        unrealized_pnl : float, optional
            Unrealized paper P&L.

        reason : str, optional
            Human-readable event reason.

        details : dict, optional
            Additional structured information.

        timestamp : str, optional
            Explicit event timestamp. When omitted, the
            configured timestamp factory is used.

        Returns
        -------
        dict
            Defensive copy of the recorded event.
        """

        normalized_event = (
            self._validate_event(
                event
            )
        )

        normalized_status = (
            self._normalize_status(
                status
            )
        )

        normalized_price = (
            self._validate_optional_price(
                price
            )
        )

        normalized_realized_pnl = (
            self._validate_optional_number(
                realized_pnl,
                "realized_pnl",
            )
        )

        normalized_unrealized_pnl = (
            self._validate_optional_number(
                unrealized_pnl,
                "unrealized_pnl",
            )
        )

        normalized_reason = (
            self._normalize_reason(
                reason
            )
        )

        normalized_details = (
            self._validate_details(
                details
            )
        )

        if timestamp is None:
            resolved_timestamp = (
                self._timestamp_factory()
            )

        else:
            resolved_timestamp = (
                timestamp
            )

        if resolved_timestamp is None:
            raise ValueError(
                "timestamp must not be None."
            )

        resolved_timestamp = str(
            resolved_timestamp
        ).strip()

        if not resolved_timestamp:
            raise ValueError(
                "timestamp must not be empty."
            )

        audit_event = {
            "sequence": (
                len(
                    self._events
                )
                + 1
            ),
            "timestamp": (
                resolved_timestamp
            ),
            "trade_id": (
                self.trade_id
            ),
            "event": (
                normalized_event
            ),
            "status": (
                normalized_status
            ),
            "price": (
                normalized_price
            ),
            "realized_pnl": (
                normalized_realized_pnl
            ),
            "unrealized_pnl": (
                normalized_unrealized_pnl
            ),
            "reason": (
                normalized_reason
            ),
            "details": (
                normalized_details
            ),
        }

        self._events.append(
            audit_event
        )

        return deepcopy(
            audit_event
        )

    def record_opened(
        self,
        price,
        status="OPEN",
        details=None,
        timestamp=None,
    ):
        """
        Record a paper trade opening event.
        """

        return self.record(
            event=(
                PaperTradeLifecycleEvent.OPENED
            ),
            status=status,
            price=price,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            reason=(
                "Paper trade opened."
            ),
            details=details,
            timestamp=timestamp,
        )

    def record_price_updated(
        self,
        price,
        unrealized_pnl,
        status="OPEN",
        details=None,
        timestamp=None,
    ):
        """
        Record a paper trade price update.
        """

        return self.record(
            event=(
                PaperTradeLifecycleEvent.PRICE_UPDATED
            ),
            status=status,
            price=price,
            unrealized_pnl=(
                unrealized_pnl
            ),
            details=details,
            timestamp=timestamp,
        )

    def record_stop_loss_hit(
        self,
        price,
        realized_pnl=None,
        status="CLOSED",
        details=None,
        timestamp=None,
    ):
        """
        Record a paper stop-loss event.
        """

        return self.record(
            event=(
                PaperTradeLifecycleEvent.STOP_LOSS_HIT
            ),
            status=status,
            price=price,
            realized_pnl=(
                realized_pnl
            ),
            reason=(
                "Paper trade stop loss reached."
            ),
            details=details,
            timestamp=timestamp,
        )

    def record_target_hit(
        self,
        price,
        realized_pnl=None,
        status="CLOSED",
        details=None,
        timestamp=None,
    ):
        """
        Record a paper target event.
        """

        return self.record(
            event=(
                PaperTradeLifecycleEvent.TARGET_HIT
            ),
            status=status,
            price=price,
            realized_pnl=(
                realized_pnl
            ),
            reason=(
                "Paper trade target reached."
            ),
            details=details,
            timestamp=timestamp,
        )

    def record_closed(
        self,
        price,
        realized_pnl,
        reason=None,
        status="CLOSED",
        details=None,
        timestamp=None,
    ):
        """
        Record the final paper trade closure event.
        """

        return self.record(
            event=(
                PaperTradeLifecycleEvent.CLOSED
            ),
            status=status,
            price=price,
            realized_pnl=(
                realized_pnl
            ),
            unrealized_pnl=None,
            reason=reason,
            details=details,
            timestamp=timestamp,
        )

    def get_events(
        self,
    ):
        """
        Return defensive copies of all lifecycle events.
        """

        return deepcopy(
            self._events
        )

    def latest_event(
        self,
    ):
        """
        Return the latest lifecycle event.

        Returns None when no events exist.
        """

        if not self._events:
            return None

        return deepcopy(
            self._events[
                -1
            ]
        )

    def count_events(
        self,
    ):
        """
        Return the number of recorded events.
        """

        return len(
            self._events
        )

    def build_summary(
        self,
    ):
        """
        Build a complete lifecycle audit summary.
        """

        events = (
            self.get_events()
        )

        latest = (
            events[-1]
            if events
            else None
        )

        return {
            "trade_id": (
                self.trade_id
            ),
            "event_count": (
                len(
                    events
                )
            ),
            "latest_event": (
                latest.get(
                    "event"
                )
                if latest
                else None
            ),
            "latest_status": (
                latest.get(
                    "status"
                )
                if latest
                else None
            ),
            "events": events,
        }

    def clear(
        self,
    ):
        """
        Clear in-memory lifecycle events.

        This does not affect any persistent journal.
        """

        self._events.clear()