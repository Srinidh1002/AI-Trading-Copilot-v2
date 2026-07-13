"""
Historical paper-trade performance analytics.

Analyses CLOSED paper trades only and produces descriptive
performance statistics for historical-learning context.

IMPORTANT:
- Analytics only.
- Does not place orders.
- Does not modify live trading decisions.
- Historical performance must not override live safety gates.
"""

from collections import defaultdict


class HistoricalTradePerformanceEngine:

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
            or minimum_sample_size < 1
        ):
            raise ValueError(
                "minimum_sample_size must be a positive integer."
            )

        self.minimum_sample_size = (
            minimum_sample_size
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def analyse(
        self,
        trades,
    ):
        """
        Analyse closed historical paper trades.
        """

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

        closed_trades = [
            trade
            for trade in trades
            if self._trade_value(
                trade,
                "status",
            )
            == "CLOSED"
        ]

        overall = self._calculate_metrics(
            closed_trades
        )

        return {
            "overall": overall,
            "by_strategy": self._group_metrics(
                closed_trades,
                self._snapshot_value(
                    "strategy"
                ),
            ),
            "by_market_regime": self._group_metrics(
                closed_trades,
                self._snapshot_value(
                    "market_regime"
                ),
            ),
            "by_direction": self._group_metrics(
                closed_trades,
                lambda trade: self._trade_value(
                    trade,
                    "direction",
                ),
            ),
            "by_volume_bias": self._group_metrics(
                closed_trades,
                self._snapshot_value(
                    "volume_bias"
                ),
            ),
            "by_volume_spike": self._group_metrics(
                closed_trades,
                self._snapshot_value(
                    "volume_spike"
                ),
            ),
            "minimum_sample_size": (
                self.minimum_sample_size
            ),
        }

    def find_similar(
        self,
        trades,
        decision_snapshot,
    ):
        """
        Find closed trades matching current decision context.

        Matching uses available strategy, regime, direction,
        volume bias, and setup type.

        Missing current fields are ignored.
        """

        if not isinstance(
            decision_snapshot,
            dict,
        ):
            raise ValueError(
                "decision_snapshot must be a dictionary."
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

        matching_fields = (
            "strategy",
            "market_regime",
            "direction",
            "volume_bias",
            "trigger_type",
        )

        expected = {
            field: decision_snapshot.get(
                field
            )
            for field in matching_fields
            if decision_snapshot.get(
                field
            )
            is not None
        }

        similar = []

        for trade in trades:

            if (
                self._trade_value(
                    trade,
                    "status",
                )
                != "CLOSED"
            ):
                continue

            snapshot = (
                self._decision_snapshot(
                    trade
                )
            )

            matches = True

            for field, value in (
                expected.items()
            ):
                if field == "direction":
                    candidate = (
                        snapshot.get(
                            field
                        )
                    )

                    if candidate is None:
                        candidate = (
                            self._trade_value(
                                trade,
                                "direction",
                            )
                        )

                else:
                    candidate = (
                        snapshot.get(
                            field
                        )
                    )

                if candidate != value:
                    matches = False
                    break

            if matches:
                similar.append(
                    trade
                )

        return {
            "matching_fields": expected,
            "metrics": self._calculate_metrics(
                similar
            ),
        }

    # ========================================================
    # METRICS
    # ========================================================

    def _calculate_metrics(
        self,
        trades,
    ):
        pnl_values = []

        for trade in trades:

            pnl = self._trade_value(
                trade,
                "realized_pnl",
            )

            if pnl is None:
                continue

            try:
                pnl = float(
                    pnl
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            pnl_values.append(
                pnl
            )

        total_trades = len(
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
            total_trades
            - wins
            - losses
        )

        total_pnl = sum(
            pnl_values
        )

        average_pnl = (
            total_pnl / total_trades
            if total_trades
            else 0.0
        )

        win_rate = (
            (wins / total_trades) * 100
            if total_trades
            else 0.0
        )

        average_win = (
            sum(
                pnl
                for pnl in pnl_values
                if pnl > 0
            )
            / wins
            if wins
            else 0.0
        )

        average_loss = (
            sum(
                pnl
                for pnl in pnl_values
                if pnl < 0
            )
            / losses
            if losses
            else 0.0
        )

        loss_rate = (
            losses / total_trades
            if total_trades
            else 0.0
        )

        win_probability = (
            wins / total_trades
            if total_trades
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

        sufficient_sample = (
            total_trades
            >= self.minimum_sample_size
        )

        return {
            "total_trades": total_trades,
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
            "sufficient_sample": (
                sufficient_sample
            ),
        }

    def _group_metrics(
        self,
        trades,
        key_function,
    ):
        groups = defaultdict(
            list
        )

        for trade in trades:

            key = key_function(
                trade
            )

            if key is None:
                continue

            groups[
                str(key)
            ].append(
                trade
            )

        return {
            key: self._calculate_metrics(
                grouped_trades
            )
            for key, grouped_trades
            in groups.items()
        }

    # ========================================================
    # DATA ACCESS
    # ========================================================

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
        snapshot = (
            cls._metadata(
                trade
            ).get(
                "decision_snapshot"
            )
        )

        return (
            snapshot
            if isinstance(
                snapshot,
                dict,
            )
            else {}
        )

    @classmethod
    def _snapshot_value(
        cls,
        field,
    ):
        def getter(
            trade,
        ):
            return (
                cls._decision_snapshot(
                    trade
                ).get(
                    field
                )
            )

        return getter