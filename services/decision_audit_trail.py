"""
Decision audit-trail service.

Creates a structured, append-only record of the major
decision stages in the live trading pipeline.

The audit trail is informational only.
It does not authorize trades and does not place orders.
"""

from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)


class DecisionAuditTrail:
    """
    Record the decision path taken by a trading pipeline.

    Each audit event contains:
    - sequence number
    - stage
    - status
    - decision
    - reasons
    - optional details
    - timestamp

    The returned audit data is copied so external callers
    cannot accidentally mutate the internal audit history.
    """

    def __init__(
        self,
        timestamp_factory=None,
    ):
        self._timestamp_factory = (
            timestamp_factory
            if timestamp_factory is not None
            else self._utc_timestamp
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
    def _normalize_text(
        value,
        default,
    ):
        """
        Normalize a text field into a non-empty string.
        """

        if value is None:
            return default

        text = str(
            value
        ).strip()

        if not text:
            return default

        return text.upper()

    @staticmethod
    def _normalize_reasons(
        reasons,
    ):
        """
        Normalize reasons into a list of non-empty strings.
        """

        if reasons is None:
            return []

        if isinstance(
            reasons,
            str,
        ):
            reasons = [
                reasons
            ]

        elif not isinstance(
            reasons,
            (
                list,
                tuple,
                set,
            ),
        ):
            reasons = [
                reasons
            ]

        normalized = []

        for reason in reasons:

            if reason is None:
                continue

            text = str(
                reason
            ).strip()

            if not text:
                continue

            normalized.append(
                text
            )

        return normalized

    def record(
        self,
        stage,
        status,
        decision=None,
        reasons=None,
        details=None,
    ):
        """
        Append one event to the audit trail.

        Parameters
        ----------
        stage : str
            Pipeline stage name.

        status : str
            Stage result such as:
            PASSED, FAILED, BLOCKED, WAITING, COMPLETED.

        decision : str, optional
            Decision produced at this stage.

        reasons : list[str] or str, optional
            Human-readable explanations.

        details : dict, optional
            Additional structured information.

        Returns
        -------
        dict
            A copy of the recorded event.
        """

        normalized_stage = (
            self._normalize_text(
                stage,
                "UNKNOWN_STAGE",
            )
        )

        normalized_status = (
            self._normalize_text(
                status,
                "UNKNOWN",
            )
        )

        normalized_decision = None

        if decision is not None:

            normalized_decision = (
                self._normalize_text(
                    decision,
                    "UNKNOWN",
                )
            )

        normalized_reasons = (
            self._normalize_reasons(
                reasons
            )
        )

        if details is None:
            normalized_details = {}

        elif isinstance(
            details,
            dict,
        ):
            normalized_details = (
                deepcopy(
                    details
                )
            )

        else:
            raise TypeError(
                "Audit event details must be a dictionary."
            )

        timestamp = (
            self._timestamp_factory()
        )

        event = {
            "sequence": (
                len(
                    self._events
                )
                + 1
            ),
            "timestamp": str(
                timestamp
            ),
            "stage": normalized_stage,
            "status": normalized_status,
            "decision": normalized_decision,
            "reasons": normalized_reasons,
            "details": normalized_details,
        }

        self._events.append(
            event
        )

        return deepcopy(
            event
        )

    def get_events(
        self,
    ):
        """
        Return a copy of all recorded audit events.
        """

        return deepcopy(
            self._events
        )

    def latest_event(
        self,
    ):
        """
        Return the latest audit event.

        Returns None when no events have been recorded.
        """

        if not self._events:
            return None

        return deepcopy(
            self._events[
                -1
            ]
        )

    def clear(
        self,
    ):
        """
        Remove all recorded audit events.
        """

        self._events.clear()

    def build_summary(
        self,
        final_decision=None,
    ):
        """
        Build a complete structured audit summary.
        """

        events = self.get_events()

        if final_decision is None:

            latest = (
                events[-1]
                if events
                else None
            )

            resolved_final_decision = (
                latest.get(
                    "decision"
                )
                if latest
                else None
            )

        else:

            resolved_final_decision = (
                self._normalize_text(
                    final_decision,
                    "UNKNOWN",
                )
            )

        return {
            "final_decision": (
                resolved_final_decision
            ),
            "event_count": (
                len(
                    events
                )
            ),
            "events": events,
        }