"""
Market Session Summary Engine.

Reads persisted MarketCycleJournal entries and produces
read-only session-level market intelligence.

Architecture:

MarketCycleJournal
    -> cycles.jsonl
        -> MarketSessionSummaryEngine
            -> session statistics
            -> decision distributions
            -> direction distributions
            -> regime distributions
            -> strategy distributions
            -> confidence statistics
            -> risk-flag frequencies
            -> setup statistics
            -> paper-trading statistics
            -> decision transitions
            -> trade-ready timing

IMPORTANT:
- READ ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify pipeline results.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime


class MarketSessionSummaryEngine:
    """
    Summarize one market session from journal entries.
    """

    UNKNOWN = "UNKNOWN"

    def _safe_list(
        self,
        value,
    ):
        if isinstance(
            value,
            list,
        ):
            return value

        return []

    def _normalize_label(
        self,
        value,
    ):
        if value is None:
            return self.UNKNOWN

        text = str(
            value
        ).strip()

        if not text:
            return self.UNKNOWN

        return text

    def _safe_number(
        self,
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            return float(
                value
            )

        return None

    def _safe_timestamp(
        self,
        value,
    ):
        if not isinstance(
            value,
            str,
        ):
            return None

        normalized = (
            value
            .strip()
        )

        if not normalized:
            return None

        try:
            return datetime.fromisoformat(
                normalized.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return None

    def _distribution(
        self,
        entries,
        field,
    ):
        counter = Counter()

        for entry in entries:
            value = self._normalize_label(
                entry.get(
                    field
                )
            )

            counter[
                value
            ] += 1

        return dict(
            sorted(
                counter.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        )

    def _dominant_value(
        self,
        distribution,
    ):
        if not distribution:
            return None

        known_items = [
            (
                key,
                value,
            )
            for (
                key,
                value,
            )
            in distribution.items()
            if key != self.UNKNOWN
        ]

        if not known_items:
            return None

        return max(
            known_items,
            key=lambda item: (
                item[1],
                item[0],
            ),
        )[0]

    def _confidence_statistics(
        self,
        entries,
        *,
        field_name="confidence",
        fallback_field_name=None,
    ):
        values = []

        for entry in entries:
            raw_value = entry.get(
                field_name
            )

            if (
                raw_value is None
                and fallback_field_name
                is not None
            ):
                raw_value = entry.get(
                    fallback_field_name
                )

            value = self._safe_number(
                raw_value
            )

            if value is not None:
                values.append(
                    value
                )

        if not values:
            return {
                "observations": 0,
                "average": None,
                "minimum": None,
                "maximum": None,
            }

        return {
            "observations": len(
                values
            ),
            "average": round(
                sum(
                    values
                )
                / len(
                    values
                ),
                2,
            ),
            "minimum": min(
                values
            ),
            "maximum": max(
                values
            ),
        }

    def _evidence_strength_label_distribution(
        self,
        entries,
    ):
        return self._distribution(
            entries,
            "evidence_strength_label",
        )

    def _risk_flag_frequency(
        self,
        entries,
    ):
        counter = Counter()

        for entry in entries:
            flags = self._safe_list(
                entry.get(
                    "risk_flags"
                )
            )

            for flag in flags:
                normalized = (
                    self._normalize_label(
                        flag
                    )
                )

                if normalized == self.UNKNOWN:
                    continue

                counter[
                    normalized
                ] += 1

        return dict(
            sorted(
                counter.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        )

    def _paper_trading_statistics(
        self,
        entries,
    ):
        status_counter = Counter()

        opened = 0

        for entry in entries:
            status = self._normalize_label(
                entry.get(
                    "paper_trade_status"
                )
            )

            status_counter[
                status
            ] += 1

            if (
                entry.get(
                    "paper_trade_opened"
                )
                is True
            ):
                opened += 1

        return {
            "opened": opened,
            "not_opened": (
                len(
                    entries
                )
                - opened
            ),
            "status_distribution": dict(
                sorted(
                    status_counter.items(),
                    key=lambda item: (
                        -item[1],
                        item[0],
                    ),
                )
            ),
        }

    def _decision_transitions(
        self,
        entries,
    ):
        transitions = Counter()

        previous_decision = None

        for entry in entries:
            decision = self._normalize_label(
                entry.get(
                    "decision"
                )
            )

            if (
                previous_decision is not None
                and decision != previous_decision
            ):
                transition = (
                    f"{previous_decision}"
                    f" -> "
                    f"{decision}"
                )

                transitions[
                    transition
                ] += 1

            previous_decision = (
                decision
            )

        return {
            "count": sum(
                transitions.values()
            ),
            "distribution": dict(
                sorted(
                    transitions.items(),
                    key=lambda item: (
                        -item[1],
                        item[0],
                    ),
                )
            ),
        }

    def _trade_ready_timing(
        self,
        entries,
    ):
        trade_ready_entries = []

        for entry in entries:
            decision = self._normalize_label(
                entry.get(
                    "decision"
                )
            )

            market_decision = (
                self._normalize_label(
                    entry.get(
                        "market_decision"
                    )
                )
            )

            if (
                decision == "TRADE_READY"
                or market_decision == "TRADE_READY"
            ):
                timestamp = self._safe_timestamp(
                    entry.get(
                        "timestamp"
                    )
                )

                if timestamp is not None:
                    trade_ready_entries.append(
                        timestamp
                    )

        if not trade_ready_entries:
            return {
                "count": 0,
                "first_timestamp": None,
                "last_timestamp": None,
            }

        ordered = sorted(
            trade_ready_entries
        )

        return {
            "count": len(
                ordered
            ),
            "first_timestamp": (
                ordered[
                    0
                ].isoformat()
            ),
            "last_timestamp": (
                ordered[
                    -1
                ].isoformat()
            ),
        }

    def _session_timing(
        self,
        entries,
    ):
        timestamps = []

        for entry in entries:
            timestamp = self._safe_timestamp(
                entry.get(
                    "timestamp"
                )
            )

            if timestamp is not None:
                timestamps.append(
                    timestamp
                )

        if not timestamps:
            return {
                "first_timestamp": None,
                "last_timestamp": None,
                "duration_seconds": None,
            }

        ordered = sorted(
            timestamps
        )

        first_timestamp = (
            ordered[
                0
            ]
        )

        last_timestamp = (
            ordered[
                -1
            ]
        )

        return {
            "first_timestamp": (
                first_timestamp.isoformat()
            ),
            "last_timestamp": (
                last_timestamp.isoformat()
            ),
            "duration_seconds": round(
                (
                    last_timestamp
                    - first_timestamp
                ).total_seconds(),
                3,
            ),
        }

    def summarize(
        self,
        entries,
        *,
        session_date=None,
    ):
        """
        Build one read-only session summary.
        """

        if not isinstance(
            entries,
            list,
        ):
            raise ValueError(
                "entries must be a list."
            )

        normalized_entries = []

        for entry in entries:
            if not isinstance(
                entry,
                dict,
            ):
                raise ValueError(
                    "Every journal entry must be a dictionary."
                )

            normalized_entries.append(
                deepcopy(
                    entry
                )
            )

        resolved_session_date = (
            session_date
        )

        if (
            resolved_session_date
            is None
            and normalized_entries
        ):
            resolved_session_date = (
                normalized_entries[
                    0
                ].get(
                    "session_date"
                )
            )

        decision_distribution = (
            self._distribution(
                normalized_entries,
                "decision",
            )
        )

        market_decision_distribution = (
            self._distribution(
                normalized_entries,
                "market_decision",
            )
        )

        direction_distribution = (
            self._distribution(
                normalized_entries,
                "direction",
            )
        )

        regime_distribution = (
            self._distribution(
                normalized_entries,
                "market_regime",
            )
        )

        strategy_distribution = (
            self._distribution(
                normalized_entries,
                "strategy",
            )
        )

        setup_distribution = (
            self._distribution(
                normalized_entries,
                "setup_status",
            )
        )

        session_status_distribution = (
            self._distribution(
                normalized_entries,
                "market_session_status",
            )
        )

        summary = {
            "status": "COMPLETED",
            "read_only": True,
            "session_date": (
                resolved_session_date
            ),
            "cycles_observed": len(
                normalized_entries
            ),
            "decisions": {
                "distribution": (
                    decision_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        decision_distribution
                    )
                ),
            },
            "market_decisions": {
                "distribution": (
                    market_decision_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        market_decision_distribution
                    )
                ),
            },
            "directions": {
                "distribution": (
                    direction_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        direction_distribution
                    )
                ),
            },
            "regimes": {
                "distribution": (
                    regime_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        regime_distribution
                    )
                ),
            },
            "strategies": {
                "distribution": (
                    strategy_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        strategy_distribution
                    )
                ),
            },
            "confidence": (
                self._confidence_statistics(
                    normalized_entries,
                    field_name=(
                        "direction_confidence"
                    ),
                    fallback_field_name=(
                        "confidence"
                    ),
                )
            ),
            "direction_confidence": (
                self._confidence_statistics(
                    normalized_entries,
                    field_name=(
                        "direction_confidence"
                    ),
                    fallback_field_name=(
                        "confidence"
                    ),
                )
            ),
            "evidence_strength": (
                self._confidence_statistics(
                    normalized_entries,
                    field_name=(
                        "evidence_strength_score"
                    ),
                )
            ),
            "evidence_strength_labels": {
                "distribution": (
                    self._evidence_strength_label_distribution(
                        normalized_entries
                    )
                ),
                "dominant": (
                    self._dominant_value(
                        self._evidence_strength_label_distribution(
                            normalized_entries
                        )
                    )
                ),
            },
            "risk_flags": (
                self._risk_flag_frequency(
                    normalized_entries
                )
            ),
            "setups": {
                "distribution": (
                    setup_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        setup_distribution
                    )
                ),
            },
            "paper_trading": (
                self._paper_trading_statistics(
                    normalized_entries
                )
            ),
            "decision_transitions": (
                self._decision_transitions(
                    normalized_entries
                )
            ),
            "trade_ready_timing": (
                self._trade_ready_timing(
                    normalized_entries
                )
            ),
            "session_timing": (
                self._session_timing(
                    normalized_entries
                )
            ),
            "market_session_statuses": {
                "distribution": (
                    session_status_distribution
                ),
                "dominant": (
                    self._dominant_value(
                        session_status_distribution
                    )
                ),
            },
        }

        return deepcopy(
            summary
        )
