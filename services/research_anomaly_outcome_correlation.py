"""
Read-only research intelligence for correlating observed anomaly
patterns with historical closed paper-trade outcomes.

This service has no execution authority.

It must never:

- place or modify an order
- authorize or reject a trade
- change a market decision
- change confidence
- change risk
- change position sizing
- change stop loss
- mutate paper-trading state

Correlation is research evidence only and does not imply causation.
"""

from copy import deepcopy
from datetime import date, datetime


class ResearchAnomalyOutcomeCorrelation:
    """
    Correlate session-level research anomalies with closed historical
    paper-trade outcomes.
    """

    def analyze(
        self,
        sessions,
        trades,
    ):
        """
        Analyse anomaly-to-outcome correlation.

        A trade is eligible only when:

        - status == "CLOSED"
        - realized_pnl is numeric
        - a session date can be resolved

        Session anomaly codes are read from:

        research_anomaly_intelligence.anomaly_codes
        """

        if sessions is None:
            raise ValueError(
                "sessions must not be None."
            )

        if not isinstance(
            sessions,
            (list, tuple),
        ):
            raise ValueError(
                "sessions must be a list or tuple."
            )

        if trades is None:
            raise ValueError(
                "trades must not be None."
            )

        if not isinstance(
            trades,
            (list, tuple),
        ):
            raise ValueError(
                "trades must be a list or tuple."
            )

        session_records = (
            self._build_session_records(
                sessions
            )
        )

        closed_trade_records = (
            self._build_closed_trade_records(
                trades
            )
        )

        trades_by_session = {}

        for trade_record in closed_trade_records:
            session_date = (
                trade_record["session_date"]
            )

            trades_by_session.setdefault(
                session_date,
                [],
            ).append(
                trade_record
            )

        anomaly_sessions = {}

        for session_record in session_records:
            session_date = (
                session_record["session_date"]
            )

            for code in session_record[
                "anomaly_codes"
            ]:
                anomaly_sessions.setdefault(
                    code,
                    [],
                ).append(
                    session_date
                )

        anomaly_correlations = []

        for code in sorted(
            anomaly_sessions
        ):
            observed_session_dates = (
                anomaly_sessions[code]
            )

            linked_trades = []

            for session_date in (
                observed_session_dates
            ):
                linked_trades.extend(
                    trades_by_session.get(
                        session_date,
                        [],
                    )
                )

            metrics = self._calculate_metrics(
                linked_trades
            )

            anomaly_correlations.append(
                {
                    "code": code,
                    "anomaly_sessions": len(
                        observed_session_dates
                    ),
                    "session_dates": list(
                        observed_session_dates
                    ),
                    "linked_closed_trades": (
                        metrics[
                            "linked_closed_trades"
                        ]
                    ),
                    "linked_trade_outcomes": deepcopy(
                        linked_trades
                    ),
                    "wins": metrics["wins"],
                    "losses": metrics["losses"],
                    "flat": metrics["flat"],
                    "win_rate_percent": metrics[
                        "win_rate_percent"
                    ],
                    "loss_rate_percent": metrics[
                        "loss_rate_percent"
                    ],
                    "flat_rate_percent": metrics[
                        "flat_rate_percent"
                    ],
                    "total_realized_pnl": metrics[
                        "total_realized_pnl"
                    ],
                    "average_realized_pnl": (
                        metrics[
                            "average_realized_pnl"
                        ]
                    ),
                    "minimum_realized_pnl": (
                        metrics[
                            "minimum_realized_pnl"
                        ]
                    ),
                    "maximum_realized_pnl": (
                        metrics[
                            "maximum_realized_pnl"
                        ]
                    ),
                    "outcome_state": (
                        self._outcome_state(
                            metrics
                        )
                    ),
                }
            )

        combination_correlations = (
            self._combination_correlations(
                session_records,
                trades_by_session,
            )
        )

        research_observations = (
            self._research_observations(
                anomaly_correlations,
                combination_correlations,
                session_records,
                closed_trade_records,
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "correlation_not_causation": True,
            "sessions_observed": len(
                session_records
            ),
            "closed_trades_observed": len(
                closed_trade_records
            ),
            "unique_anomaly_codes": len(
                anomaly_correlations
            ),
            "anomaly_correlations": (
                anomaly_correlations
            ),
            "combination_correlations": (
                combination_correlations
            ),
            "research_observations": (
                research_observations
            ),
            "session_records": deepcopy(
                session_records
            ),
            "closed_trade_records": deepcopy(
                closed_trade_records
            ),
        }

    def _build_session_records(
        self,
        sessions,
    ):
        records = []

        for index, session in enumerate(
            sessions
        ):
            if not isinstance(
                session,
                dict,
            ):
                continue

            session_date = self._session_date(
                session
            )

            if session_date is None:
                continue

            anomaly_intelligence = session.get(
                "research_anomaly_intelligence"
            )

            if not isinstance(
                anomaly_intelligence,
                dict,
            ):
                anomaly_intelligence = {}

            anomaly_codes = (
                anomaly_intelligence.get(
                    "anomaly_codes"
                )
            )

            if not isinstance(
                anomaly_codes,
                (list, tuple, set),
            ):
                anomaly_codes = []

            normalized_codes = sorted(
                {
                    str(code).strip()
                    for code in anomaly_codes
                    if str(code).strip()
                }
            )

            records.append(
                {
                    "index": index,
                    "session_date": session_date,
                    "anomaly_codes": (
                        normalized_codes
                    ),
                }
            )

        records.sort(
            key=lambda item: (
                item["session_date"],
                item["index"],
            )
        )

        return records

    def _build_closed_trade_records(
        self,
        trades,
    ):
        records = []

        for index, trade in enumerate(
            trades
        ):
            status = self._trade_value(
                trade,
                "status",
            )

            if status != "CLOSED":
                continue

            realized_pnl = self._trade_value(
                trade,
                "realized_pnl",
            )

            try:
                realized_pnl = float(
                    realized_pnl
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            session_date = (
                self._trade_session_date(
                    trade
                )
            )

            if session_date is None:
                continue

            if realized_pnl > 0:
                outcome = "WIN"
            elif realized_pnl < 0:
                outcome = "LOSS"
            else:
                outcome = "FLAT"

            records.append(
                {
                    "index": index,
                    "session_date": session_date,
                    "realized_pnl": (
                        realized_pnl
                    ),
                    "outcome": outcome,
                }
            )

        records.sort(
            key=lambda item: (
                item["session_date"],
                item["index"],
            )
        )

        return records

    def _combination_correlations(
        self,
        session_records,
        trades_by_session,
    ):
        combinations = {}

        for session_record in session_records:
            codes = tuple(
                session_record["anomaly_codes"]
            )

            if len(codes) < 2:
                continue

            session_date = (
                session_record["session_date"]
            )

            item = combinations.setdefault(
                codes,
                {
                    "codes": list(codes),
                    "session_dates": [],
                    "trades": [],
                },
            )

            item["session_dates"].append(
                session_date
            )

            item["trades"].extend(
                trades_by_session.get(
                    session_date,
                    [],
                )
            )

        results = []

        for codes in sorted(
            combinations
        ):
            item = combinations[codes]

            metrics = self._calculate_metrics(
                item["trades"]
            )

            results.append(
                {
                    "codes": list(codes),
                    "anomaly_sessions": len(
                        item["session_dates"]
                    ),
                    "session_dates": list(
                        item["session_dates"]
                    ),
                    "linked_closed_trades": (
                        metrics[
                            "linked_closed_trades"
                        ]
                    ),
                     "linked_trade_outcomes": deepcopy(
                        item["trades"]
                    ),
                    "wins": metrics["wins"],
                    "losses": metrics["losses"],
                    "flat": metrics["flat"],
                    "win_rate_percent": metrics[
                        "win_rate_percent"
                    ],
                    "loss_rate_percent": metrics[
                        "loss_rate_percent"
                    ],
                    "flat_rate_percent": metrics[
                        "flat_rate_percent"
                    ],
                    "total_realized_pnl": metrics[
                        "total_realized_pnl"
                    ],
                    "average_realized_pnl": (
                        metrics[
                            "average_realized_pnl"
                        ]
                    ),
                    "minimum_realized_pnl": (
                        metrics[
                            "minimum_realized_pnl"
                        ]
                    ),
                    "maximum_realized_pnl": (
                        metrics[
                            "maximum_realized_pnl"
                        ]
                    ),
                    "outcome_state": (
                        self._outcome_state(
                            metrics
                        )
                    ),
                }
            )

        return results

    @staticmethod
    def _calculate_metrics(
        trade_records,
    ):
        pnl_values = [
            item["realized_pnl"]
            for item in trade_records
        ]

        linked_closed_trades = len(
            pnl_values
        )

        wins = sum(
            1
            for pnl in pnl_values
            if pnl > 0
        )

        losses = sum(
            1
            for pnl in pnl_values
            if pnl < 0
        )

        flat = sum(
            1
            for pnl in pnl_values
            if pnl == 0
        )

        if linked_closed_trades:
            win_rate_percent = round(
                (
                    wins
                    / linked_closed_trades
                )
                * 100,
                4,
            )

            loss_rate_percent = round(
                (
                    losses
                    / linked_closed_trades
                )
                * 100,
                4,
            )

            flat_rate_percent = round(
                (
                    flat
                    / linked_closed_trades
                )
                * 100,
                4,
            )

            total_realized_pnl = round(
                sum(pnl_values),
                4,
            )

            average_realized_pnl = round(
                (
                    total_realized_pnl
                    / linked_closed_trades
                ),
                4,
            )

            minimum_realized_pnl = min(
                pnl_values
            )

            maximum_realized_pnl = max(
                pnl_values
            )

        else:
            win_rate_percent = None
            loss_rate_percent = None
            flat_rate_percent = None
            total_realized_pnl = 0.0
            average_realized_pnl = None
            minimum_realized_pnl = None
            maximum_realized_pnl = None

        return {
            "linked_closed_trades": (
                linked_closed_trades
            ),
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "win_rate_percent": (
                win_rate_percent
            ),
            "loss_rate_percent": (
                loss_rate_percent
            ),
            "flat_rate_percent": (
                flat_rate_percent
            ),
            "total_realized_pnl": (
                total_realized_pnl
            ),
            "average_realized_pnl": (
                average_realized_pnl
            ),
            "minimum_realized_pnl": (
                minimum_realized_pnl
            ),
            "maximum_realized_pnl": (
                maximum_realized_pnl
            ),
        }

    @staticmethod
    def _outcome_state(
        metrics,
    ):
        if (
            metrics[
                "linked_closed_trades"
            ]
            == 0
        ):
            return "INSUFFICIENT_DATA"

        average_pnl = metrics[
            "average_realized_pnl"
        ]

        if average_pnl > 0:
            return "POSITIVE_CORRELATION"

        if average_pnl < 0:
            return "NEGATIVE_CORRELATION"

        return "NEUTRAL_CORRELATION"

    def _research_observations(
        self,
        anomaly_correlations,
        combination_correlations,
        session_records,
        closed_trade_records,
    ):
        observations = []

        if not session_records:
            observations.append(
                "No research sessions were available "
                "for anomaly outcome correlation."
            )

            return observations

        if not anomaly_correlations:
            observations.append(
                "No anomaly codes were observed across "
                "the available research sessions."
            )

        if not closed_trade_records:
            observations.append(
                "No eligible closed trades with realized "
                "P&L were available for outcome correlation."
            )

        negative = [
            item
            for item in anomaly_correlations
            if item["outcome_state"]
            == "NEGATIVE_CORRELATION"
        ]

        positive = [
            item
            for item in anomaly_correlations
            if item["outcome_state"]
            == "POSITIVE_CORRELATION"
        ]

        if negative:
            strongest_negative = min(
                negative,
                key=lambda item: (
                    item[
                        "average_realized_pnl"
                    ],
                    item["code"],
                ),
            )

            observations.append(
                f"{strongest_negative['code']} "
                "showed the most negative average "
                "closed-trade P&L among observed "
                "anomaly correlations."
            )

        if positive:
            strongest_positive = max(
                positive,
                key=lambda item: (
                    item[
                        "average_realized_pnl"
                    ],
                    item["code"],
                ),
            )

            observations.append(
                f"{strongest_positive['code']} "
                "showed the most positive average "
                "closed-trade P&L among observed "
                "anomaly correlations."
            )

        recurring_combinations = [
            item
            for item in combination_correlations
            if item["anomaly_sessions"] > 1
        ]

        if recurring_combinations:
            observations.append(
                "At least one multi-anomaly combination "
                "was observed across multiple sessions "
                "and linked to closed-trade outcomes."
            )

        if (
            anomaly_correlations
            and all(
                item[
                    "linked_closed_trades"
                ]
                == 0
                for item in anomaly_correlations
            )
        ):
            observations.append(
                "Observed anomalies could not yet be "
                "linked to eligible closed trades."
            )

        return observations

    def _trade_session_date(
        self,
        trade,
    ):
        direct_fields = (
            "session_date",
            "closed_at",
            "exit_time",
            "updated_at",
            "timestamp",
        )

        for field in direct_fields:
            normalized = self._normalize_date(
                self._trade_value(
                    trade,
                    field,
                )
            )

            if normalized is not None:
                return normalized

        metadata = self._metadata(
            trade
        )

        for field in direct_fields:
            normalized = self._normalize_date(
                metadata.get(field)
            )

            if normalized is not None:
                return normalized

        decision_snapshot = (
            self._decision_snapshot(
                trade
            )
        )

        for field in direct_fields:
            normalized = self._normalize_date(
                decision_snapshot.get(
                    field
                )
            )

            if normalized is not None:
                return normalized

        return None

    def _session_date(
        self,
        session,
    ):
        direct_fields = (
            "session_date",
            "date",
        )

        for field in direct_fields:
            normalized = self._normalize_date(
                session.get(field)
            )

            if normalized is not None:
                return normalized

        snapshot = session.get(
            "research_snapshot"
        )

        if isinstance(
            snapshot,
            dict,
        ):
            for field in direct_fields:
                normalized = (
                    self._normalize_date(
                        snapshot.get(field)
                    )
                )

                if normalized is not None:
                    return normalized

        return None

    @staticmethod
    def _normalize_date(
        value,
    ):
        if isinstance(
            value,
            datetime,
        ):
            return value.date().isoformat()

        if isinstance(
            value,
            date,
        ):
            return value.isoformat()

        if not isinstance(
            value,
            str,
        ):
            return None

        value = value.strip()

        if not value:
            return None

        try:
            return date.fromisoformat(
                value
            ).isoformat()
        except ValueError:
            pass

        try:
            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            ).date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _trade_value(
        trade,
        field,
    ):
        if isinstance(
            trade,
            dict,
        ):
            return trade.get(
                field
            )

        return getattr(
            trade,
            field,
            None,
        )

    @classmethod
    def _metadata(
        cls,
        trade,
    ):
        metadata = cls._trade_value(
            trade,
            "metadata",
        )

        return (
            metadata
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

    @classmethod
    def _decision_snapshot(
        cls,
        trade,
    ):
        snapshot = cls._metadata(
            trade
        ).get(
            "decision_snapshot"
        )

        return (
            snapshot
            if isinstance(
                snapshot,
                dict,
            )
            else {}
        )