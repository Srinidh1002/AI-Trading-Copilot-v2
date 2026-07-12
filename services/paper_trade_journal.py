"""
Persistent append-only journal for paper-trade lifecycle events.

The journal stores one JSON object per line using JSON Lines
(JSONL) format.

This service:
- is paper-trading only
- is append-only
- does not place real orders
- does not call broker order APIs
- does not authorize live trades
"""

from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)
import json
from pathlib import Path


class PaperTradeJournal:
    """
    Persist and retrieve paper-trade lifecycle events.

    Each journal record contains:
    - logged_at
    - trade_id
    - event
    - status
    - lifecycle_event

    Records are written in append-only JSONL format.
    """

    DEFAULT_PATH = (
        Path("data")
        / "paper_trading"
        / "paper_trade_journal.jsonl"
    )

    def __init__(
        self,
        file_path=None,
        timestamp_factory=None,
    ):
        self.file_path = Path(
            file_path
            if file_path is not None
            else self.DEFAULT_PATH
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

    @staticmethod
    def _utc_timestamp():
        """
        Return a timezone-aware UTC timestamp.
        """

        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

    @staticmethod
    def _validate_non_empty_string(
        value,
        field_name,
    ):
        """
        Validate and normalize a required string.
        """

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field_name} must be a non-empty string."
            )

        normalized = (
            value.strip()
        )

        if not normalized:
            raise ValueError(
                f"{field_name} must be a non-empty string."
            )

        return normalized

    @classmethod
    def _validate_lifecycle_event(
        cls,
        lifecycle_event,
    ):
        """
        Validate a lifecycle event dictionary.
        """

        if not isinstance(
            lifecycle_event,
            dict,
        ):
            raise TypeError(
                "lifecycle_event must be a dictionary."
            )

        event_copy = deepcopy(
            lifecycle_event
        )

        trade_id = (
            cls._validate_non_empty_string(
                event_copy.get(
                    "trade_id"
                ),
                "trade_id",
            )
        )

        event = (
            cls._validate_non_empty_string(
                event_copy.get(
                    "event"
                ),
                "event",
            )
            .upper()
        )

        sequence = event_copy.get(
            "sequence"
        )

        if (
            isinstance(
                sequence,
                bool,
            )
            or not isinstance(
                sequence,
                int,
            )
            or sequence < 1
        ):
            raise ValueError(
                "lifecycle_event sequence must be "
                "an integer greater than or equal to 1."
            )

        timestamp = (
            cls._validate_non_empty_string(
                event_copy.get(
                    "timestamp"
                ),
                "timestamp",
            )
        )

        details = event_copy.get(
            "details",
            {},
        )

        if details is None:
            details = {}

        if not isinstance(
            details,
            dict,
        ):
            raise TypeError(
                "lifecycle_event details must be a dictionary."
            )

        event_copy[
            "trade_id"
        ] = trade_id

        event_copy[
            "event"
        ] = event

        event_copy[
            "timestamp"
        ] = timestamp

        event_copy[
            "details"
        ] = deepcopy(
            details
        )

        return event_copy

    def build_record(
        self,
        lifecycle_event,
        metadata=None,
    ):
        """
        Build a validated persistent journal record.

        Parameters
        ----------
        lifecycle_event : dict
            Event produced by PaperTradeLifecycleAudit.

        metadata : dict, optional
            Additional paper-trading context.

        Returns
        -------
        dict
            Defensive copy of the journal record.
        """

        validated_event = (
            self._validate_lifecycle_event(
                lifecycle_event
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
                "metadata must be a dictionary."
            )

        logged_at = (
            self._timestamp_factory()
        )

        if logged_at is None:
            raise ValueError(
                "Journal timestamp must not be None."
            )

        logged_at = str(
            logged_at
        ).strip()

        if not logged_at:
            raise ValueError(
                "Journal timestamp must not be empty."
            )

        record = {
            "logged_at": logged_at,
            "trade_id": (
                validated_event[
                    "trade_id"
                ]
            ),
            "event": (
                validated_event[
                    "event"
                ]
            ),
            "status": (
                validated_event.get(
                    "status"
                )
            ),
            "metadata": (
                normalized_metadata
            ),
            "lifecycle_event": (
                validated_event
            ),
        }

        return deepcopy(
            record
        )

    def log(
        self,
        lifecycle_event,
        metadata=None,
    ):
        """
        Append one lifecycle event to the journal.

        The file is never overwritten.
        """

        record = self.build_record(
            lifecycle_event=(
                lifecycle_event
            ),
            metadata=metadata,
        )

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        serialized = json.dumps(
            record,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        with self.file_path.open(
            "a",
            encoding="utf-8",
        ) as journal_file:
            journal_file.write(
                serialized
            )

            journal_file.write(
                "\n"
            )

        return deepcopy(
            record
        )

    def read_records(
        self,
    ):
        """
        Read and validate all journal records.

        Returns an empty list when the journal file
        does not exist.

        Malformed JSON fails closed with ValueError.
        """

        if not self.file_path.exists():
            return []

        records = []

        with self.file_path.open(
            "r",
            encoding="utf-8",
        ) as journal_file:

            for (
                line_number,
                line,
            ) in enumerate(
                journal_file,
                start=1,
            ):
                stripped = (
                    line.strip()
                )

                if not stripped:
                    continue

                try:
                    record = (
                        json.loads(
                            stripped
                        )
                    )

                except (
                    json.JSONDecodeError
                ) as exc:
                    raise ValueError(
                        "Invalid JSON in paper-trade "
                        f"journal at line {line_number}."
                    ) from exc

                if not isinstance(
                    record,
                    dict,
                ):
                    raise ValueError(
                        "Paper-trade journal record "
                        f"at line {line_number} "
                        "must be a dictionary."
                    )

                lifecycle_event = (
                    record.get(
                        "lifecycle_event"
                    )
                )

                validated_event = (
                    self._validate_lifecycle_event(
                        lifecycle_event
                    )
                )

                record_trade_id = (
                    self._validate_non_empty_string(
                        record.get(
                            "trade_id"
                        ),
                        "trade_id",
                    )
                )

                record_event = (
                    self._validate_non_empty_string(
                        record.get(
                            "event"
                        ),
                        "event",
                    )
                    .upper()
                )

                if (
                    record_trade_id
                    != validated_event[
                        "trade_id"
                    ]
                ):
                    raise ValueError(
                        "Journal trade_id does not match "
                        "lifecycle_event trade_id at "
                        f"line {line_number}."
                    )

                if (
                    record_event
                    != validated_event[
                        "event"
                    ]
                ):
                    raise ValueError(
                        "Journal event does not match "
                        "lifecycle_event event at "
                        f"line {line_number}."
                    )

                metadata = record.get(
                    "metadata",
                    {},
                )

                if metadata is None:
                    metadata = {}

                if not isinstance(
                    metadata,
                    dict,
                ):
                    raise ValueError(
                        "Journal metadata at line "
                        f"{line_number} must be "
                        "a dictionary."
                    )

                normalized_record = (
                    deepcopy(
                        record
                    )
                )

                normalized_record[
                    "trade_id"
                ] = record_trade_id

                normalized_record[
                    "event"
                ] = record_event

                normalized_record[
                    "metadata"
                ] = deepcopy(
                    metadata
                )

                normalized_record[
                    "lifecycle_event"
                ] = validated_event

                records.append(
                    normalized_record
                )

        return deepcopy(
            records
        )

    def get_recent_records(
        self,
        limit=10,
    ):
        """
        Return the most recent journal records.

        Records remain in chronological order from
        oldest to newest within the selected result.
        """

        if (
            isinstance(
                limit,
                bool,
            )
            or not isinstance(
                limit,
                int,
            )
            or limit < 1
        ):
            raise ValueError(
                "limit must be an integer greater "
                "than or equal to 1."
            )

        records = (
            self.read_records()
        )

        return deepcopy(
            records[
                -limit:
            ]
        )

    def get_records_for_trade(
        self,
        trade_id,
    ):
        """
        Return all journal records for one paper trade.
        """

        normalized_trade_id = (
            self._validate_non_empty_string(
                trade_id,
                "trade_id",
            )
        )

        records = (
            self.read_records()
        )

        matching = [
            record
            for record in records
            if record.get(
                "trade_id"
            )
            == normalized_trade_id
        ]

        return deepcopy(
            matching
        )

    def get_records_by_event(
        self,
        event,
    ):
        """
        Return all records matching a lifecycle event.
        """

        normalized_event = (
            self._validate_non_empty_string(
                event,
                "event",
            )
            .upper()
        )

        records = (
            self.read_records()
        )

        matching = [
            record
            for record in records
            if record.get(
                "event"
            )
            == normalized_event
        ]

        return deepcopy(
            matching
        )

    def count_records(
        self,
    ):
        """
        Return the total number of valid journal records.
        """

        return len(
            self.read_records()
        )