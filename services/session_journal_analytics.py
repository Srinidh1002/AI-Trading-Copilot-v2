"""
Session Journal Analytics Engine.

Analyzes persisted MarketCycleJournal entries to understand
how the AI Trading Copilot behaved during one market session.

Research questions include:

- How often was a trade opportunity observed?
- Which risk flags appeared most frequently?
- How persistent was market direction?
- How persistent was the detected market regime?
- How did confidence differ by decision?
- When did TRADE_READY decisions occur?
- How often did the decision state change?

IMPORTANT:
- READ ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from collections import Counter
from copy import deepcopy


class SessionJournalAnalyticsEngine:
    """
    Build read-only analytics from market-cycle journal entries.
    """

    TRADE_READY_DECISIONS = {
        "TRADE_READY",
        "TRADE",
        "BUY",
        "SELL",
    }

    UNKNOWN = "UNKNOWN"

    def _normalize_entries(
        self,
        entries,
    ):
        if entries is None:
            return []

        if not isinstance(
            entries,
            (
                list,
                tuple,
            ),
        ):
            raise ValueError(
                "entries must be a list or tuple."
            )

        normalized = []

        for entry in entries:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            normalized.append(
                deepcopy(
                    entry
                )
            )

        return normalized

    def _normalize_label(
        self,
        value,
    ):
        if value is None:
            return self.UNKNOWN

        normalized = str(
            value
        ).strip()

        if not normalized:
            return self.UNKNOWN

        return normalized.upper()

    def _extract_decision(
        self,
        entry,
    ):
        return self._normalize_label(
            entry.get(
                "decision"
            )
        )

    def _extract_direction(
        self,
        entry,
    ):
        return self._normalize_label(
            entry.get(
                "direction"
            )
        )

    def _extract_regime(
        self,
        entry,
    ):
        regime = entry.get(
            "regime"
        )

        if isinstance(
            regime,
            dict,
        ):
            regime = (
                regime.get(
                    "primary_regime"
                )
                or regime.get(
                    "regime"
                )
                or regime.get(
                    "name"
                )
            )

        return self._normalize_label(
            regime
        )

    def _extract_confidence(
        self,
        entry,
    ):
        confidence = entry.get(
            "confidence"
        )

        if confidence is None:
            strategy = entry.get(
                "strategy"
            )

            if isinstance(
                strategy,
                dict,
            ):
                confidence = strategy.get(
                    "confidence"
                )

        if isinstance(
            confidence,
            bool,
        ):
            return None

        try:
            return float(
                confidence
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _extract_risk_flags(
        self,
        entry,
    ):
        risk_flags = entry.get(
            "risk_flags"
        )

        if risk_flags is None:
            strategy = entry.get(
                "strategy"
            )

            if isinstance(
                strategy,
                dict,
            ):
                risk_flags = strategy.get(
                    "risk_flags"
                )

        if risk_flags is None:
            return []

        if isinstance(
            risk_flags,
            str,
        ):
            risk_flags = [
                risk_flags,
            ]

        if not isinstance(
            risk_flags,
            (
                list,
                tuple,
                set,
            ),
        ):
            return []

        normalized = []

        for risk_flag in risk_flags:
            if risk_flag is None:
                continue

            value = str(
                risk_flag
            ).strip()

            if not value:
                continue

            normalized.append(
                value
            )

        return normalized

    def _extract_timestamp(
        self,
        entry,
    ):
        value = (
            entry.get(
                "timestamp"
            )
            or entry.get(
                "recorded_at"
            )
            or entry.get(
                "created_at"
            )
        )

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return (
            normalized
            if normalized
            else None
        )

    def _build_distribution(
        self,
        values,
    ):
        return dict(
            Counter(
                values
            )
        )

    def _build_longest_sequences(
        self,
        values,
    ):
        """
        Return the longest consecutive sequence for every value.
        """

        longest = {}

        current_value = None
        current_count = 0

        for value in values:
            if value == current_value:
                current_count += 1

            else:
                current_value = value
                current_count = 1

            previous_longest = longest.get(
                value,
                0,
            )

            if current_count > previous_longest:
                longest[
                    value
                ] = current_count

        return longest

    def _build_confidence_by_decision(
        self,
        entries,
    ):
        confidence_values = {}

        for entry in entries:
            decision = self._extract_decision(
                entry
            )

            confidence = self._extract_confidence(
                entry
            )

            if confidence is None:
                continue

            confidence_values.setdefault(
                decision,
                [],
            ).append(
                confidence
            )

        result = {}

        for (
            decision,
            values,
        ) in confidence_values.items():
            result[
                decision
            ] = {
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

        return result

    def _build_decision_transitions(
        self,
        decisions,
    ):
        transitions = Counter()

        previous = None

        for decision in decisions:
            if (
                previous is not None
                and decision != previous
            ):
                transition = (
                    f"{previous} -> {decision}"
                )

                transitions[
                    transition
                ] += 1

            previous = decision

        return {
            "count": sum(
                transitions.values()
            ),
            "distribution": dict(
                transitions
            ),
        }

    def _build_trade_ready_events(
        self,
        entries,
    ):
        events = []

        for (
            index,
            entry,
        ) in enumerate(
            entries
        ):
            decision = self._extract_decision(
                entry
            )

            if (
                decision
                not in self.TRADE_READY_DECISIONS
            ):
                continue

            events.append(
                {
                    "index": index,
                    "timestamp": (
                        self._extract_timestamp(
                            entry
                        )
                    ),
                    "decision": decision,
                    "direction": (
                        self._extract_direction(
                            entry
                        )
                    ),
                    "regime": (
                        self._extract_regime(
                            entry
                        )
                    ),
                    "confidence": (
                        self._extract_confidence(
                            entry
                        )
                    ),
                }
            )

        return events

    def analyze(
        self,
        entries,
        *,
        session_date=None,
    ):
        """
        Analyze one market-session journal.
        """

        normalized_entries = (
            self._normalize_entries(
                entries
            )
        )

        decisions = [
            self._extract_decision(
                entry
            )
            for entry in normalized_entries
        ]

        directions = [
            self._extract_direction(
                entry
            )
            for entry in normalized_entries
        ]

        regimes = [
            self._extract_regime(
                entry
            )
            for entry in normalized_entries
        ]

        trade_ready_count = sum(
            1
            for decision in decisions
            if (
                decision
                in self.TRADE_READY_DECISIONS
            )
        )

        total_cycles = len(
            normalized_entries
        )

        no_trade_count = (
            total_cycles
            - trade_ready_count
        )

        opportunity_rate = (
            round(
                (
                    trade_ready_count
                    / total_cycles
                )
                * 100,
                2,
            )
            if total_cycles
            else 0.0
        )

        risk_flags = Counter()

        for entry in normalized_entries:
            risk_flags.update(
                self._extract_risk_flags(
                    entry
                )
            )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "session_date": session_date,
            "total_cycles": total_cycles,
            "trade_opportunity": {
                "trade_ready": (
                    trade_ready_count
                ),
                "not_trade_ready": (
                    no_trade_count
                ),
                "opportunity_rate_percent": (
                    opportunity_rate
                ),
            },
            "decision_distribution": (
                self._build_distribution(
                    decisions
                )
            ),
            "direction_distribution": (
                self._build_distribution(
                    directions
                )
            ),
            "regime_distribution": (
                self._build_distribution(
                    regimes
                )
            ),
            "top_trade_blockers": dict(
                risk_flags
            ),
            "direction_persistence": (
                self._build_longest_sequences(
                    directions
                )
            ),
            "regime_persistence": (
                self._build_longest_sequences(
                    regimes
                )
            ),
            "confidence_by_decision": (
                self._build_confidence_by_decision(
                    normalized_entries
                )
            ),
            "decision_transitions": (
                self._build_decision_transitions(
                    decisions
                )
            ),
            "trade_ready_events": (
                self._build_trade_ready_events(
                    normalized_entries
                )
            ),
        }