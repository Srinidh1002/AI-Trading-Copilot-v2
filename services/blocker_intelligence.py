"""
Blocker Intelligence Engine.

Analyzes chronological MarketCycleJournal entries to understand
which observed blockers and risk flags most frequently prevented
trade readiness.

Research questions include:

- Which blockers occur most frequently?
- How persistent are blockers across observed cycles?
- Which blockers form the longest consecutive streaks?
- How does the blocker state change between cycles?
- Which blockers disappear immediately before TRADE_READY?
- What is the final observed blocker state?

IMPORTANT:
- READ ONLY.
- RESEARCH AND OBSERVABILITY ONLY.
- DOES NOT remove blockers.
- DOES NOT override risk flags.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify live pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from collections import Counter
from copy import deepcopy


class BlockerIntelligence:
    """
    Analyze blocker persistence, transitions, and clearance.
    """

    TRADE_READY = "TRADE_READY"
    NONE = "NONE"
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

    def _normalize_blocker(
        self,
        value,
    ):
        if value is None:
            return None

        normalized = " ".join(
            str(
                value
            ).strip().split()
        )

        if not normalized:
            return None

        return normalized

    def _extract_decision(
        self,
        entry,
    ):
        return self._normalize_label(
            entry.get(
                "decision"
            )
        )

    def _extract_risk_flags(
        self,
        entry,
    ):
        risk_flags = entry.get(
            "risk_flags"
        )

        if risk_flags is None:
            market_decision = entry.get(
                "market_decision"
            )

            if isinstance(
                market_decision,
                dict,
            ):
                risk_flags = market_decision.get(
                    "risk_flags"
                )

        return self._normalize_blocker_collection(
            risk_flags
        )

    def _extract_setup_reasons(
        self,
        entry,
    ):
        setup_reasons = entry.get(
            "setup_reasons"
        )

        if setup_reasons is None:
            setup = entry.get(
                "setup"
            )

            if isinstance(
                setup,
                dict,
            ):
                setup_reasons = (
                    setup.get(
                        "reasons"
                    )
                    or setup.get(
                        "setup_reasons"
                    )
                )

        return self._normalize_blocker_collection(
            setup_reasons
        )

    def _extract_blockers(
        self,
        entry,
    ):
        explicit_blockers = entry.get(
            "blockers"
        )

        blockers = []

        blockers.extend(
            self._normalize_blocker_collection(
                explicit_blockers
            )
        )

        blockers.extend(
            self._extract_risk_flags(
                entry
            )
        )

        blockers.extend(
            self._extract_setup_reasons(
                entry
            )
        )

        unique = []

        seen = set()

        for blocker in blockers:
            key = blocker.casefold()

            if key in seen:
                continue

            seen.add(
                key
            )

            unique.append(
                blocker
            )

        return unique

    def _normalize_blocker_collection(
        self,
        values,
    ):
        if values is None:
            return []

        if isinstance(
            values,
            str,
        ):
            blocker = self._normalize_blocker(
                values
            )

            return (
                [
                    blocker,
                ]
                if blocker
                else []
            )

        if isinstance(
            values,
            (
                list,
                tuple,
                set,
            ),
        ):
            normalized = []

            for value in values:
                blocker = self._normalize_blocker(
                    value
                )

                if blocker:
                    normalized.append(
                        blocker
                    )

            return normalized

        return []

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

    def _build_cycle_state(
        self,
        entry,
        index,
    ):
        blockers = self._extract_blockers(
            entry
        )

        return {
            "index": index,
            "timestamp": (
                self._extract_timestamp(
                    entry
                )
            ),
            "decision": (
                self._extract_decision(
                    entry
                )
            ),
            "blockers": blockers,
            "blocked": bool(
                blockers
            ),
            "blocker_count": len(
                blockers
            ),
        }

    def _build_blocker_statistics(
        self,
        cycle_states,
    ):
        cycle_count = len(
            cycle_states
        )

        occurrence_counter = Counter()

        blocked_cycle_counter = Counter()

        for state in cycle_states:
            blockers = state[
                "blockers"
            ]

            occurrence_counter.update(
                blockers
            )

            for blocker in set(
                blockers
            ):
                blocked_cycle_counter[
                    blocker
                ] += 1

        statistics = []

        for (
            blocker,
            occurrences,
        ) in occurrence_counter.most_common():
            blocked_cycles = (
                blocked_cycle_counter[
                    blocker
                ]
            )

            persistence_percent = (
                round(
                    (
                        blocked_cycles
                        / cycle_count
                    )
                    * 100.0,
                    2,
                )
                if cycle_count
                else 0.0
            )

            statistics.append(
                {
                    "blocker": blocker,
                    "occurrences": occurrences,
                    "blocked_cycles": blocked_cycles,
                    "persistence_percent": (
                        persistence_percent
                    ),
                }
            )

        return statistics

    def _state_key(
        self,
        blockers,
    ):
        if not blockers:
            return self.NONE

        return " | ".join(
            sorted(
                blockers,
                key=str.casefold,
            )
        )

    def _build_transitions(
        self,
        cycle_states,
    ):
        counter = Counter()

        for (
            previous,
            current,
        ) in zip(
            cycle_states,
            cycle_states[
                1:
            ],
        ):
            previous_key = self._state_key(
                previous[
                    "blockers"
                ]
            )

            current_key = self._state_key(
                current[
                    "blockers"
                ]
            )

            if previous_key == current_key:
                continue

            counter[
                (
                    previous_key,
                    current_key,
                )
            ] += 1

        return [
            {
                "from": source,
                "to": destination,
                "count": count,
            }
            for (
                source,
                destination,
            ), count in counter.most_common()
        ]

    def _build_cleared_before_trade_ready(
        self,
        cycle_states,
    ):
        counter = Counter()

        for (
            previous,
            current,
        ) in zip(
            cycle_states,
            cycle_states[
                1:
            ],
        ):
            if (
                current[
                    "decision"
                ]
                != self.TRADE_READY
            ):
                continue

            previous_blockers = set(
                previous[
                    "blockers"
                ]
            )

            current_blockers = set(
                current[
                    "blockers"
                ]
            )

            cleared = (
                previous_blockers
                - current_blockers
            )

            counter.update(
                cleared
            )

        return [
            {
                "blocker": blocker,
                "count": count,
            }
            for (
                blocker,
                count,
            ) in counter.most_common()
        ]

    def _build_longest_blocker_streak(
        self,
        cycle_states,
    ):
        longest_blocker = None
        longest_cycles = 0
        longest_start_index = None
        longest_end_index = None

        active = {}

        for state in cycle_states:
            index = state[
                "index"
            ]

            blockers = set(
                state[
                    "blockers"
                ]
            )

            next_active = {}

            for blocker in blockers:
                if blocker in active:
                    start_index = active[
                        blocker
                    ][
                        "start_index"
                    ]

                    cycles = (
                        active[
                            blocker
                        ][
                            "cycles"
                        ]
                        + 1
                    )

                else:
                    start_index = index
                    cycles = 1

                next_active[
                    blocker
                ] = {
                    "start_index": start_index,
                    "cycles": cycles,
                }

                if cycles > longest_cycles:
                    longest_blocker = blocker
                    longest_cycles = cycles
                    longest_start_index = (
                        start_index
                    )
                    longest_end_index = index

            active = next_active

        return {
            "blocker": longest_blocker,
            "cycles": longest_cycles,
            "start_index": longest_start_index,
            "end_index": longest_end_index,
        }

    def analyze(
        self,
        entries,
        *,
        session_date=None,
    ):
        """
        Analyze observed blocker intelligence.
        """

        normalized_entries = (
            self._normalize_entries(
                entries
            )
        )

        cycle_states = [
            self._build_cycle_state(
                entry,
                index,
            )
            for (
                index,
                entry,
            ) in enumerate(
                normalized_entries
            )
        ]

        blocked_cycles = sum(
            1
            for state in cycle_states
            if state[
                "blocked"
            ]
        )

        trade_ready_cycles = sum(
            1
            for state in cycle_states
            if state[
                "decision"
            ]
            == self.TRADE_READY
        )

        final_blockers = (
            deepcopy(
                cycle_states[
                    -1
                ][
                    "blockers"
                ]
            )
            if cycle_states
            else []
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "session_date": session_date,
            "cycles_observed": len(
                cycle_states
            ),
            "blocked_cycles": blocked_cycles,
            "unblocked_cycles": (
                len(
                    cycle_states
                )
                - blocked_cycles
            ),
            "trade_ready_cycles": (
                trade_ready_cycles
            ),
            "blocker_statistics": (
                self._build_blocker_statistics(
                    cycle_states
                )
            ),
            "blocker_transitions": (
                self._build_transitions(
                    cycle_states
                )
            ),
            "cleared_before_trade_ready": (
                self._build_cleared_before_trade_ready(
                    cycle_states
                )
            ),
            "longest_blocker_streak": (
                self._build_longest_blocker_streak(
                    cycle_states
                )
            ),
            "final_blocker_state": {
                "blockers": final_blockers,
                "blocked": bool(
                    final_blockers
                ),
                "state": self._state_key(
                    final_blockers
                ),
            },
            "cycle_states": cycle_states,
        }