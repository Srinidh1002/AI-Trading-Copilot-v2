"""
Market cycle intelligence journal.

Persists structured, append-only market-cycle observations for
post-market analysis.

The journal is an observability component only.

It must never:

- change a live market decision
- authorize a trade
- reject a trade
- modify risk logic
- modify paper-trading state
- place a real order

Storage format:

data/
    market_sessions/
        YYYY-MM-DD/
            cycles.jsonl

Each journal entry is stored as one JSON object per line.
"""

import json
from copy import deepcopy
from datetime import (
    date,
    datetime,
    timezone,
)
from pathlib import Path
from threading import Lock


class MarketCycleJournal:
    """
    Append-only structured market-cycle journal.
    """

    DEFAULT_BASE_DIRECTORY = (
        Path("data")
        / "market_sessions"
    )

    FILE_NAME = "cycles.jsonl"

    def __init__(
        self,
        base_directory=None,
    ):
        if base_directory is None:
            base_directory = (
                self.DEFAULT_BASE_DIRECTORY
            )

        self.base_directory = Path(
            base_directory
        )

        self._write_lock = Lock()

    @staticmethod
    def _safe_dict(
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    @staticmethod
    def _safe_list(
        value,
    ):
        if isinstance(
            value,
            list,
        ):
            return deepcopy(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                deepcopy(
                    value
                )
            )

        return []

    @staticmethod
    def _normalize_timestamp(
        value,
    ):
        if value is None:
            return (
                datetime.now(
                    timezone.utc
                )
                .isoformat()
            )

        if isinstance(
            value,
            datetime,
        ):
            if value.tzinfo is None:
                value = value.replace(
                    tzinfo=timezone.utc
                )

            return value.isoformat()

        if isinstance(
            value,
            str,
        ):
            normalized = (
                value.strip()
            )

            if not normalized:
                raise ValueError(
                    "timestamp cannot be empty."
                )

            return normalized

        raise ValueError(
            "timestamp must be a datetime, string, or None."
        )

    @staticmethod
    def _resolve_session_date(
        timestamp,
        session_date=None,
    ):
        if session_date is not None:
            if isinstance(
                session_date,
                datetime,
            ):
                return (
                    session_date
                    .date()
                    .isoformat()
                )

            if isinstance(
                session_date,
                date,
            ):
                return (
                    session_date
                    .isoformat()
                )

            if isinstance(
                session_date,
                str,
            ):
                normalized = (
                    session_date.strip()
                )

                try:
                    return (
                        date.fromisoformat(
                            normalized
                        )
                        .isoformat()
                    )

                except ValueError as exc:
                    raise ValueError(
                        "session_date must use YYYY-MM-DD format."
                    ) from exc

            raise ValueError(
                "session_date must be a date, datetime, string, or None."
            )

        try:
            parsed_timestamp = (
                datetime.fromisoformat(
                    timestamp.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except ValueError as exc:
            raise ValueError(
                "timestamp must be ISO-8601 compatible when "
                "session_date is not provided."
            ) from exc

        return (
            parsed_timestamp
            .date()
            .isoformat()
        )

    def build_entry(
        self,
        *,
        pipeline_result,
        paper_trading_result=None,
        timestamp=None,
        session_date=None,
        metadata=None,
    ):
        """
        Build one compact market-cycle journal entry.

        This method does not write to disk.
        """

        if not isinstance(
            pipeline_result,
            dict,
        ):
            raise ValueError(
                "pipeline_result must be a dictionary."
            )

        normalized_timestamp = (
            self._normalize_timestamp(
                timestamp
            )
        )

        normalized_session_date = (
            self._resolve_session_date(
                normalized_timestamp,
                session_date=(
                    session_date
                ),
            )
        )

        market_analysis = (
            self._safe_dict(
                pipeline_result.get(
                    "market_analysis"
                )
            )
        )

        strategy = (
            self._safe_dict(
                market_analysis.get(
                    "strategy"
                )
            )
        )

        regime = (
            self._safe_dict(
                market_analysis.get(
                    "regime"
                )
            )
        )

        timeframe = (
            self._safe_dict(
                market_analysis.get(
                    "timeframe"
                )
            )
        )

        technical = (
            self._safe_dict(
                market_analysis.get(
                    "technical"
                )
            )
        )

        volume = (
            self._safe_dict(
                market_analysis.get(
                    "volume"
                )
            )
        )

        setup_trigger = (
            self._safe_dict(
                pipeline_result.get(
                    "setup_trigger"
                )
            )
        )

        contract = (
            self._safe_dict(
                pipeline_result.get(
                    "contract"
                )
            )
        )

        market_session = (
            self._safe_dict(
                pipeline_result.get(
                    "session_status"
                )
                or pipeline_result.get(
                    "market_session"
                )
                or pipeline_result.get(
                    "session_guard"
                )
            )
        )

        paper_result = (
            self._safe_dict(
                paper_trading_result
            )
        )

        normalized_metadata = (
            deepcopy(
                metadata
            )
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

        entry = {
            "timestamp": (
                normalized_timestamp
            ),
            "session_date": (
                normalized_session_date
            ),
            "decision": (
                pipeline_result.get(
                    "decision"
                )
            ),
            "market_decision": (
                pipeline_result.get(
                    "market_decision"
                )
            ),
            "direction": (
                pipeline_result.get(
                    "direction"
                )
            ),
            "strategy": (
                strategy.get(
                    "strategy"
                )
            ),
            "strategy_decision": (
                strategy.get(
                    "decision"
                )
            ),
            "confidence": (
                strategy.get(
                    "confidence"
                )
            ),
            "risk_flags": (
                self._safe_list(
                    strategy.get(
                        "risk_flags"
                    )
                )
            ),
            "market_regime": (
                regime.get(
                    "primary_regime"
                )
            ),
            "regime_trend": (
                regime.get(
                    "trend"
                )
            ),
            "regime_confidence": (
                regime.get(
                    "confidence"
                )
            ),
            "timeframe_trend": (
                timeframe.get(
                    "overall_trend"
                )
            ),
            "timeframe_alignment": (
                timeframe.get(
                    "alignment"
                )
            ),
            "timeframe_confidence": (
                timeframe.get(
                    "confidence"
                )
            ),
            "technical_trend": (
                technical.get(
                    "trend"
                )
            ),
            "technical_score": (
                technical.get(
                    "score"
                )
            ),
            "technical_confidence": (
                technical.get(
                    "confidence"
                )
            ),
            "volume_bias": (
                volume.get(
                    "bias"
                )
            ),
            "relative_volume": (
                volume.get(
                    "relative_volume"
                )
            ),
            "volume_spike": (
                volume.get(
                    "volume_spike"
                )
            ),
            "setup_status": (
                setup_trigger.get(
                    "status"
                )
            ),
            "setup_direction": (
                setup_trigger.get(
                    "direction"
                )
            ),
            "trigger_type": (
                setup_trigger.get(
                    "trigger_type"
                )
            ),
            "trigger_price": (
                setup_trigger.get(
                    "trigger_price"
                )
            ),
            "option_symbol": (
                contract.get(
                    "symbol"
                )
            ),
            "option_type": (
                contract.get(
                    "option_type"
                )
            ),
            "strike": (
                contract.get(
                    "strike"
                )
            ),
            "expiry": (
                contract.get(
                    "expiry"
                )
            ),
            "market_session_status": (
                market_session.get(
                    "status"
                )
            ),
            "market_open": (
                market_session.get(
                    "market_open"
                )
            ),
            "paper_trade_status": (
                paper_result.get(
                    "status"
                )
            ),
            "paper_trade_opened": (
                paper_result.get(
                    "opened",
                    False,
                )
            ),
            "paper_trade_id": (
                paper_result.get(
                    "trade_id"
                )
            ),
            "paper_trade_reason": (
                paper_result.get(
                    "reason"
                )
            ),
            "metadata": (
                normalized_metadata
            ),
        }

        return deepcopy(
            entry
        )

    def get_session_directory(
        self,
        session_date,
    ):
        normalized_session_date = (
            self._resolve_session_date(
                (
                    datetime.now(
                        timezone.utc
                    )
                    .isoformat()
                ),
                session_date=(
                    session_date
                ),
            )
        )

        return (
            self.base_directory
            / normalized_session_date
        )

    def get_journal_path(
        self,
        session_date,
    ):
        return (
            self.get_session_directory(
                session_date
            )
            / self.FILE_NAME
        )

    def append_entry(
        self,
        entry,
    ):
        """
        Append one entry to the JSONL journal.

        Returns a deep copy of the persisted entry.
        """

        if not isinstance(
            entry,
            dict,
        ):
            raise ValueError(
                "entry must be a dictionary."
            )

        session_date = (
            entry.get(
                "session_date"
            )
        )

        if not session_date:
            raise ValueError(
                "entry must contain session_date."
            )

        journal_path = (
            self.get_journal_path(
                session_date
            )
        )

        serialized = json.dumps(
            entry,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )

        with self._write_lock:
            journal_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with journal_path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as journal_file:
                journal_file.write(
                    serialized
                )

                journal_file.write(
                    "\n"
                )

                journal_file.flush()

        return deepcopy(
            entry
        )

    def record_cycle(
        self,
        *,
        pipeline_result,
        paper_trading_result=None,
        timestamp=None,
        session_date=None,
        metadata=None,
    ):
        """
        Build and append one market-cycle entry.
        """

        entry = (
            self.build_entry(
                pipeline_result=(
                    pipeline_result
                ),
                paper_trading_result=(
                    paper_trading_result
                ),
                timestamp=(
                    timestamp
                ),
                session_date=(
                    session_date
                ),
                metadata=(
                    metadata
                ),
            )
        )

        return (
            self.append_entry(
                entry
            )
        )

    def read_entries(
        self,
        session_date,
    ):
        """
        Read all valid journal entries for one session.

        Empty or missing journals return an empty list.
        """

        journal_path = (
            self.get_journal_path(
                session_date
            )
        )

        if not journal_path.exists():
            return []

        entries = []

        with journal_path.open(
            "r",
            encoding="utf-8",
        ) as journal_file:
            for line_number, line in enumerate(
                journal_file,
                start=1,
            ):
                normalized = (
                    line.strip()
                )

                if not normalized:
                    continue

                try:
                    entry = json.loads(
                        normalized
                    )

                except json.JSONDecodeError as exc:
                    raise ValueError(
                        (
                            "Invalid market-cycle journal JSON "
                            f"at line {line_number}."
                        )
                    ) from exc

                if not isinstance(
                    entry,
                    dict,
                ):
                    raise ValueError(
                        (
                            "Market-cycle journal entry "
                            f"at line {line_number} "
                            "must be a JSON object."
                        )
                    )

                entries.append(
                    entry
                )

        return deepcopy(
            entries
        )