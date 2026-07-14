"""
Strategy-Regime Performance Engine.

Analyzes CLOSED historical paper trades by the combination of:

    market regime
        +
    strategy

The engine is a specialized cross-dimensional research layer.

It does not replace HistoricalTradePerformanceEngine. The existing
historical engine remains responsible for broad historical metrics and
similar-trade research.

This engine answers a narrower research question:

    How has a strategy historically performed when observed in a
    specific market regime?

IMPORTANT:
- READ ONLY.
- HISTORICAL RESEARCH ONLY.
- PAPER-TRADE ANALYTICS ONLY.
- DOES NOT recommend a strategy.
- DOES NOT authorize a trade.
- DOES NOT reject a trade.
- DOES NOT override live safety gates.
- DOES NOT modify live pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from collections import defaultdict
from copy import deepcopy


class StrategyRegimePerformanceEngine:
    """
    Analyze CLOSED paper trades by strategy-regime combination.
    """

    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"

    def __init__(
        self,
        minimum_sample_size=5,
    ):
        if (
            not isinstance(
                minimum_sample_size,
                int,
            )
            or isinstance(
                minimum_sample_size,
                bool,
            )
            or minimum_sample_size <= 0
        ):
            raise ValueError(
                "minimum_sample_size must be a positive integer."
            )

        self.minimum_sample_size = (
            minimum_sample_size
        )

    def _normalize_trades(
        self,
        trades,
    ):
        if trades is None:
            raise ValueError(
                "trades must not be None."
            )

        if not isinstance(
            trades,
            (
                list,
                tuple,
            ),
        ):
            raise ValueError(
                "trades must be a list or tuple."
            )

        normalized = []

        for trade in trades:
            if not isinstance(
                trade,
                dict,
            ):
                continue

            normalized.append(
                deepcopy(
                    trade
                )
            )

        return normalized

    def _trade_value(
        self,
        trade,
        key,
    ):
        if not isinstance(
            trade,
            dict,
        ):
            return None

        return trade.get(
            key
        )

    def _decision_snapshot(
        self,
        trade,
    ):
        snapshot = self._trade_value(
            trade,
            "decision_snapshot",
        )

        if isinstance(
            snapshot,
            dict,
        ):
            return snapshot

        source_decision = self._trade_value(
            trade,
            "source_decision",
        )

        if isinstance(
            source_decision,
            dict,
        ):
            nested_snapshot = (
                source_decision.get(
                    "decision_snapshot"
                )
            )

            if isinstance(
                nested_snapshot,
                dict,
            ):
                return nested_snapshot

            return source_decision

        return {}

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

    def _extract_strategy(
        self,
        trade,
    ):
        snapshot = self._decision_snapshot(
            trade
        )

        value = snapshot.get(
            "strategy"
        )

        if value is None:
            value = self._trade_value(
                trade,
                "strategy",
            )

        return self._normalize_label(
            value
        )

    def _extract_regime(
        self,
        trade,
    ):
        snapshot = self._decision_snapshot(
            trade
        )

        value = snapshot.get(
            "market_regime"
        )

        if value is None:
            value = snapshot.get(
                "regime"
            )

        if isinstance(
            value,
            dict,
        ):
            value = (
                value.get(
                    "primary_regime"
                )
                or value.get(
                    "regime"
                )
                or value.get(
                    "name"
                )
            )

        if value is None:
            value = self._trade_value(
                trade,
                "market_regime",
            )

        if value is None:
            value = self._trade_value(
                trade,
                "regime",
            )

        if isinstance(
            value,
            dict,
        ):
            value = (
                value.get(
                    "primary_regime"
                )
                or value.get(
                    "regime"
                )
                or value.get(
                    "name"
                )
            )

        return self._normalize_label(
            value
        )

    def _extract_status(
        self,
        trade,
    ):
        return self._normalize_label(
            self._trade_value(
                trade,
                "status",
            )
        )

    def _extract_realized_pnl(
        self,
        trade,
    ):
        value = self._trade_value(
            trade,
            "realized_pnl",
        )

        if value is None:
            return None

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _extract_timestamp(
        self,
        trade,
    ):
        value = (
            self._trade_value(
                trade,
                "closed_at",
            )
            or self._trade_value(
                trade,
                "updated_at",
            )
            or self._trade_value(
                trade,
                "created_at",
            )
            or self._trade_value(
                trade,
                "opened_at",
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

    def _extract_trade_id(
        self,
        trade,
    ):
        value = self._trade_value(
            trade,
            "trade_id",
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

    def _build_trade_record(
        self,
        trade,
        index,
    ):
        return {
            "index": index,
            "trade_id": (
                self._extract_trade_id(
                    trade
                )
            ),
            "status": (
                self._extract_status(
                    trade
                )
            ),
            "strategy": (
                self._extract_strategy(
                    trade
                )
            ),
            "market_regime": (
                self._extract_regime(
                    trade
                )
            ),
            "realized_pnl": (
                self._extract_realized_pnl(
                    trade
                )
            ),
            "timestamp": (
                self._extract_timestamp(
                    trade
                )
            ),
        }

    def _calculate_profit_factor(
        self,
        pnl_values,
    ):
        gross_profit = sum(
            pnl
            for pnl in pnl_values
            if pnl > 0
        )

        gross_loss = abs(
            sum(
                pnl
                for pnl in pnl_values
                if pnl < 0
            )
        )

        if gross_loss == 0:
            if gross_profit > 0:
                return None

            return 0.0

        return round(
            gross_profit / gross_loss,
            2,
        )

    def _calculate_streaks(
        self,
        records,
    ):
        longest_win_streak = 0
        longest_loss_streak = 0

        current_win_streak = 0
        current_loss_streak = 0

        for record in records:
            pnl = record[
                "realized_pnl"
            ]

            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0

                longest_win_streak = max(
                    longest_win_streak,
                    current_win_streak,
                )

            elif pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0

                longest_loss_streak = max(
                    longest_loss_streak,
                    current_loss_streak,
                )

            else:
                current_win_streak = 0
                current_loss_streak = 0

        return {
            "longest_win_streak": (
                longest_win_streak
            ),
            "longest_loss_streak": (
                longest_loss_streak
            ),
        }

    def _calculate_metrics(
        self,
        records,
    ):
        valid_records = [
            record
            for record in records
            if record[
                "realized_pnl"
            ]
            is not None
        ]

        pnl_values = [
            record[
                "realized_pnl"
            ]
            for record in valid_records
        ]

        trades = len(
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

        breakeven = (
            trades
            - wins
            - losses
        )

        total_pnl = sum(
            pnl_values
        )

        average_pnl = (
            total_pnl / trades
            if trades
            else 0.0
        )

        winning_values = [
            pnl
            for pnl in pnl_values
            if pnl > 0
        ]

        losing_values = [
            pnl
            for pnl in pnl_values
            if pnl < 0
        ]

        average_win = (
            sum(
                winning_values
            )
            / len(
                winning_values
            )
            if winning_values
            else 0.0
        )

        average_loss = (
            sum(
                losing_values
            )
            / len(
                losing_values
            )
            if losing_values
            else 0.0
        )

        win_rate = (
            (
                wins
                / trades
            )
            * 100.0
            if trades
            else 0.0
        )

        loss_rate = (
            losses / trades
            if trades
            else 0.0
        )

        win_probability = (
            wins / trades
            if trades
            else 0.0
        )

        expectancy = (
            (
                win_probability
                * average_win
            )
            + (
                loss_rate
                * average_loss
            )
        )

        streaks = (
            self._calculate_streaks(
                valid_records
            )
        )

        return {
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(
                win_rate,
                2,
            ),
            "total_pnl": round(
                total_pnl,
                2,
            ),
            "average_pnl": round(
                average_pnl,
                2,
            ),
            "average_win": round(
                average_win,
                2,
            ),
            "average_loss": round(
                average_loss,
                2,
            ),
            "expectancy": round(
                expectancy,
                2,
            ),
            "profit_factor": (
                self._calculate_profit_factor(
                    pnl_values
                )
            ),
            "longest_win_streak": (
                streaks[
                    "longest_win_streak"
                ]
            ),
            "longest_loss_streak": (
                streaks[
                    "longest_loss_streak"
                ]
            ),
            "sufficient_sample": (
                trades
                >= self.minimum_sample_size
            ),
        }

    def _build_observation(
        self,
        *,
        strategy,
        market_regime,
        metrics,
    ):
        if not metrics[
            "sufficient_sample"
        ]:
            return (
                "INSUFFICIENT_SAMPLE"
            )

        if (
            metrics[
                "total_pnl"
            ]
            > 0
            and metrics[
                "expectancy"
            ]
            > 0
        ):
            return (
                "HISTORICALLY_POSITIVE"
            )

        if (
            metrics[
                "total_pnl"
            ]
            < 0
            and metrics[
                "expectancy"
            ]
            < 0
        ):
            return (
                "HISTORICALLY_NEGATIVE"
            )

        return "HISTORICALLY_MIXED"

    def analyze(
        self,
        trades,
    ):
        """
        Analyze strategy-regime combinations from CLOSED paper trades.
        """

        normalized_trades = (
            self._normalize_trades(
                trades
            )
        )

        trade_records = [
            self._build_trade_record(
                trade,
                index,
            )
            for (
                index,
                trade,
            ) in enumerate(
                normalized_trades
            )
        ]

        closed_records = [
            record
            for record in trade_records
            if (
                record[
                    "status"
                ]
                == self.CLOSED
                and record[
                    "realized_pnl"
                ]
                is not None
            )
        ]

        groups = defaultdict(
            list
        )

        for record in closed_records:
            key = (
                record[
                    "market_regime"
                ],
                record[
                    "strategy"
                ],
            )

            groups[
                key
            ].append(
                record
            )

        combinations = []

        for (
            market_regime,
            strategy,
        ), records in groups.items():
            metrics = (
                self._calculate_metrics(
                    records
                )
            )

            combinations.append(
                {
                    "market_regime": (
                        market_regime
                    ),
                    "strategy": strategy,
                    "metrics": metrics,
                    "research_observation": (
                        self._build_observation(
                            strategy=strategy,
                            market_regime=(
                                market_regime
                            ),
                            metrics=metrics,
                        )
                    ),
                }
            )

        combinations.sort(
            key=lambda item: (
                -item[
                    "metrics"
                ][
                    "trades"
                ],
                item[
                    "market_regime"
                ],
                item[
                    "strategy"
                ],
            )
        )

        positive_combinations = [
            deepcopy(
                combination
            )
            for combination in combinations
            if (
                combination[
                    "research_observation"
                ]
                == "HISTORICALLY_POSITIVE"
            )
        ]

        negative_combinations = [
            deepcopy(
                combination
            )
            for combination in combinations
            if (
                combination[
                    "research_observation"
                ]
                == "HISTORICALLY_NEGATIVE"
            )
        ]

        sufficient_combinations = [
            combination
            for combination in combinations
            if combination[
                "metrics"
            ][
                "sufficient_sample"
            ]
        ]

        best_observed_combination = None

        if sufficient_combinations:
            best_observed_combination = (
                deepcopy(
                    max(
                        sufficient_combinations,
                        key=lambda item: (
                            item[
                                "metrics"
                            ][
                                "expectancy"
                            ],
                            item[
                                "metrics"
                            ][
                                "total_pnl"
                            ],
                            item[
                                "metrics"
                            ][
                                "win_rate"
                            ],
                        ),
                    )
                )
            )

        worst_observed_combination = None

        if sufficient_combinations:
            worst_observed_combination = (
                deepcopy(
                    min(
                        sufficient_combinations,
                        key=lambda item: (
                            item[
                                "metrics"
                            ][
                                "expectancy"
                            ],
                            item[
                                "metrics"
                            ][
                                "total_pnl"
                            ],
                            item[
                                "metrics"
                            ][
                                "win_rate"
                            ],
                        ),
                    )
                )
            )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "historical_research_only": True,
            "minimum_sample_size": (
                self.minimum_sample_size
            ),
            "trades_observed": len(
                trade_records
            ),
            "closed_trades_analyzed": len(
                closed_records
            ),
            "combinations_observed": len(
                combinations
            ),
            "combinations": combinations,
            "positive_combinations": (
                positive_combinations
            ),
            "negative_combinations": (
                negative_combinations
            ),
            "best_observed_combination": (
                best_observed_combination
            ),
            "worst_observed_combination": (
                worst_observed_combination
            ),
            "trade_records": trade_records,
        }