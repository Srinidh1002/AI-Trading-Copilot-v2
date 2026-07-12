"""
Persistent decision audit logger.

Writes completed decision audit summaries to an
append-only JSON Lines file.

Each line contains one complete audit record.

The logger is informational only.
It does not authorize trades and does not place orders.
"""

import json
from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path


class DecisionAuditLogger:
    """
    Persist trading decision audit summaries.

    Storage format:
    - JSON Lines (.jsonl)
    - One complete record per line
    - Append-only by default

    The logger creates the parent directory
    automatically when required.
    """

    def __init__(
        self,
        file_path=(
            "data/audit/"
            "decision_audit.jsonl"
        ),
        timestamp_factory=None,
    ):
        self.file_path = Path(
            file_path
        )

        self._timestamp_factory = (
            timestamp_factory
            if timestamp_factory is not None
            else self._utc_timestamp
        )

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

    def _ensure_parent_directory(
        self,
    ):
        """
        Create the audit-log parent directory
        when it does not already exist.
        """

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def _validate_audit_trail(
        audit_trail,
    ):
        """
        Validate the minimum structure required
        for a persistent audit record.
        """

        if not isinstance(
            audit_trail,
            dict,
        ):
            raise TypeError(
                "Audit trail must be a dictionary."
            )

        events = audit_trail.get(
            "events"
        )

        if not isinstance(
            events,
            list,
        ):
            raise ValueError(
                "Audit trail must contain "
                "an events list."
            )

        event_count = audit_trail.get(
            "event_count"
        )

        if event_count is None:
            raise ValueError(
                "Audit trail must contain "
                "event_count."
            )

        try:
            normalized_event_count = int(
                event_count
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Audit trail event_count "
                "must be an integer."
            ) from exc

        if (
            normalized_event_count
            != len(
                events
            )
        ):
            raise ValueError(
                "Audit trail event_count does not "
                "match the number of events."
            )

        return deepcopy(
            audit_trail
        )

    def build_record(
        self,
        audit_trail,
        metadata=None,
    ):
        """
        Build a persistent audit-log record.

        Parameters
        ----------
        audit_trail : dict
            Structured audit summary produced by
            DecisionAuditTrail.build_summary().

        metadata : dict, optional
            Additional context such as:
            - underlying
            - exchange
            - symbol token
            - spot price

        Returns
        -------
        dict
            A validated persistent record.
        """

        validated_audit = (
            self._validate_audit_trail(
                audit_trail
            )
        )

        if metadata is None:

            normalized_metadata = {}

        elif isinstance(
            metadata,
            dict,
        ):

            normalized_metadata = deepcopy(
                metadata
            )

        else:

            raise TypeError(
                "Audit metadata must be "
                "a dictionary."
            )

        return {
            "logged_at": str(
                self._timestamp_factory()
            ),
            "final_decision": (
                validated_audit.get(
                    "final_decision"
                )
            ),
            "event_count": (
                validated_audit.get(
                    "event_count",
                    0,
                )
            ),
            "metadata": (
                normalized_metadata
            ),
            "audit_trail": (
                validated_audit
            ),
        }

    def log(
        self,
        audit_trail,
        metadata=None,
    ):
        """
        Append one complete audit record
        to the JSON Lines file.

        Returns a copy of the record written.
        """

        record = self.build_record(
            audit_trail=audit_trail,
            metadata=metadata,
        )

        self._ensure_parent_directory()

        serialized = json.dumps(
            record,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        )

        with self.file_path.open(
            mode="a",
            encoding="utf-8",
        ) as file:

            file.write(
                serialized
            )

            file.write(
                "\n"
            )

        return deepcopy(
            record
        )

    def read_records(
        self,
    ):
        """
        Read all valid records from the audit log.

        Returns an empty list when the file
        does not exist.
        """

        if not self.file_path.exists():
            return []

        records = []

        with self.file_path.open(
            mode="r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                text = line.strip()

                if not text:
                    continue

                try:

                    record = json.loads(
                        text
                    )

                except json.JSONDecodeError as exc:

                    raise ValueError(
                        "Invalid JSON audit record "
                        f"at line {line_number}."
                    ) from exc

                if not isinstance(
                    record,
                    dict,
                ):
                    raise ValueError(
                        "Audit record at line "
                        f"{line_number} must be "
                        "a dictionary."
                    )

                records.append(
                    record
                )

        return records