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

    def get_recent_records(
        self,
        limit=10,
    ):
        """
        Retrieve the most recent audit records.

        Parameters
        ----------
        limit : int
            Maximum number of recent records to return.
            Must be an integer >= 1.
            Default is 10.

        Returns
        -------
        list[dict]
            The most recent records, up to `limit` records,
            in chronological order (oldest to newest).
            Returns an empty list if no records exist or
            if the audit log file does not exist.

        Raises
        ------
        ValueError
            If limit is not an integer, is a boolean,
            or is less than 1.

        Notes
        -----
        This method reuses read_records() internally,
        which means it loads and validates all records
        before returning the most recent ones.

        Invalid or malformed records are caught by
        read_records() and raise ValueError (fail-closed).

        Returned records are deep copies and cannot
        mutate persisted data.
        """

        # Validate limit is an integer but not boolean
        if isinstance(
            limit,
            bool,
        ):
            raise ValueError(
                "Limit must be an integer, not a boolean."
            )

        if not isinstance(
            limit,
            int,
        ):
            raise ValueError(
                f"Limit must be an integer, got {type(limit).__name__}."
            )

        if limit < 1:
            raise ValueError(
                f"Limit must be >= 1, got {limit}."
            )

        # Read all records (reuses existing validation)
        records = self.read_records()

        # Return the last N records in chronological order
        if not records:
            return []

        return records[-limit:]

    @staticmethod
    def _parse_timestamp(
        timestamp_str,
    ):
        """
        Parse an ISO 8601 timestamp string.

        Returns the datetime object for comparison.

        Raises ValueError if the timestamp is invalid.
        """

        try:
            # Try parsing with timezone info (preferred)
            return datetime.fromisoformat(
                timestamp_str
            )

        except (
            ValueError,
            TypeError,
        ) as exc:
            raise ValueError(
                f"Invalid timestamp format: {timestamp_str}. "
                "Expected ISO 8601 format (e.g., "
                "2026-07-12T10:00:00+00:00)."
            ) from exc

    def query_records(
        self,
        limit=None,
        final_decision=None,
        underlying=None,
        start_time=None,
        end_time=None,
    ):
        """
        Query audit records with optional filters.

        Parameters
        ----------
        limit : int, optional
            Maximum number of records to return.
            Must be >= 1. Default is None (no limit).

        final_decision : str, optional
            Filter by final decision value.
            (e.g., "TRADE_ALLOWED", "NO_TRADE").

        underlying : str, optional
            Filter by underlying asset.
            (e.g., "NIFTY", "BANKNIFTY").

        start_time : str, optional
            ISO 8601 timestamp. Return records
            logged at or after this time.

        end_time : str, optional
            ISO 8601 timestamp. Return records
            logged at or before this time.

        Returns
        -------
        list[dict]
            Records matching the filters,
            in chronological order (oldest to newest).
            Returns an empty list if no records exist
            or if no records match the filters.

        Raises
        ------
        ValueError
            If limit is invalid, or if timestamps
            are malformed.

        Notes
        -----
        All filters are optional and applied together
        (AND logic). Filtering never modifies records.
        Returned records are deep copies.
        """

        # Validate limit if provided
        if limit is not None:
            if isinstance(
                limit,
                bool,
            ):
                raise ValueError(
                    "Limit must be an integer, "
                    "not a boolean."
                )

            if not isinstance(
                limit,
                int,
            ):
                raise ValueError(
                    f"Limit must be an integer, "
                    f"got {type(limit).__name__}."
                )

            if limit < 1:
                raise ValueError(
                    f"Limit must be >= 1, got {limit}."
                )

        # Parse timestamps if provided
        start_dt = None
        end_dt = None

        if start_time is not None:
            start_dt = self._parse_timestamp(
                start_time
            )

        if end_time is not None:
            end_dt = self._parse_timestamp(
                end_time
            )

        # Read all records
        all_records = self.read_records()

        # Apply filters
        filtered = []

        for record in all_records:

            # Filter by final_decision
            if (
                final_decision is not None
                and record.get(
                    "final_decision"
                )
                != final_decision
            ):
                continue

            # Filter by underlying
            if underlying is not None:

                metadata = record.get(
                    "metadata",
                    {},
                )

                if (
                    metadata.get(
                        "underlying"
                    )
                    != underlying
                ):
                    continue

            # Filter by time range
            if (
                start_dt is not None
                or end_dt is not None
            ):

                logged_at_str = record.get(
                    "logged_at"
                )

                if logged_at_str is None:
                    continue

                try:

                    logged_at = (
                        self._parse_timestamp(
                            logged_at_str
                        )
                    )

                except ValueError:
                    # Skip records with invalid timestamps
                    continue

                if (
                    start_dt is not None
                    and logged_at < start_dt
                ):
                    continue

                if (
                    end_dt is not None
                    and logged_at > end_dt
                ):
                    continue

            filtered.append(
                record
            )

        # Apply limit
        if limit is not None:
            filtered = filtered[-limit:]

        # Return deep copies
        return [
            deepcopy(
                record
            )
            for record in filtered
        ]

    def get_summary_statistics(
        self,
        limit=None,
        final_decision=None,
        underlying=None,
        start_time=None,
        end_time=None,
    ):
        """
        Retrieve summary statistics for audit records.

        Applies the same optional filters as query_records().

        Parameters
        ----------
        limit, final_decision, underlying,
        start_time, end_time : optional
            Same as query_records().

        Returns
        -------
        dict
            Summary statistics including:
            - total_records: Count of records
            - count_by_decision: Dict of decision type -> count
            - count_by_underlying: Dict of underlying -> count
            - earliest_logged_at: ISO 8601 timestamp
            - latest_logged_at: ISO 8601 timestamp

        Notes
        -----
        Statistics are informational only and must never
        affect trading authorization.

        Missing timestamps are skipped (already filtered
        by query_records()).

        Returns empty stats if no records match the filters.
        """

        # Query records with filters
        records = self.query_records(
            limit=None,  # Get all matching records
            final_decision=final_decision,
            underlying=underlying,
            start_time=start_time,
            end_time=end_time,
        )

        # Build statistics
        stats = {
            "total_records": len(
                records
            ),
            "count_by_decision": {},
            "count_by_underlying": {},
            "earliest_logged_at": None,
            "latest_logged_at": None,
        }

        if not records:
            return stats

        # Count by decision
        for record in records:

            decision = record.get(
                "final_decision"
            )

            if decision is not None:

                stats["count_by_decision"][
                    decision
                ] = (
                    stats[
                        "count_by_decision"
                    ].get(
                        decision,
                        0,
                    )
                    + 1
                )

        # Count by underlying
        for record in records:

            metadata = record.get(
                "metadata",
                {},
            )

            underlying_val = metadata.get(
                "underlying"
            )

            if underlying_val is not None:

                stats["count_by_underlying"][
                    underlying_val
                ] = (
                    stats[
                        "count_by_underlying"
                    ].get(
                        underlying_val,
                        0,
                    )
                    + 1
                )

        # Find earliest and latest timestamps
        timestamps = []

        for record in records:

            logged_at = record.get(
                "logged_at"
            )

            if logged_at is not None:
                timestamps.append(
                    logged_at
                )

        if timestamps:

            stats["earliest_logged_at"] = (
                min(
                    timestamps
                )
            )

            stats["latest_logged_at"] = (
                max(
                    timestamps
                )
            )

        return stats