"""
Strategy Optimizer

Runs parameter optimization for trading strategies
using repeated historical backtests.

Responsibilities
----------------
✓ Parameter Grid Search
✓ Strategy Evaluation
✓ Best Parameter Selection
✓ Ranking Results
✓ Optimization Summary
"""

from __future__ import annotations

from itertools import product
from typing import Any

from services.backtesting.backtest_engine import (
    run_backtest,
)


class StrategyOptimizer:

    @staticmethod
    def optimize(
        df,
        strategy_factory,
        parameter_grid: dict[str, list[Any]],
    ) -> dict[str, Any]:

        if not parameter_grid:

            raise ValueError(
                "parameter_grid cannot be empty."
            )

        keys = list(parameter_grid.keys())

        values = [
            parameter_grid[key]
            for key in keys
        ]

        results = []

        for combination in product(*values):

            parameters = dict(
                zip(
                    keys,
                    combination,
                )
            )

            strategy = strategy_factory(
                **parameters
            )

            backtest = run_backtest(
                df,
                strategy,
            )

            result = {

                "parameters": parameters,

                "net_pnl": backtest["net_pnl"],

                "win_rate": backtest["win_rate"],

                "total_trades": backtest["total_trades"],

                "wins": backtest["wins"],

                "losses": backtest["losses"],

            }

            results.append(result)

        results.sort(

            key=lambda x: (
                x["net_pnl"],
                x["win_rate"],
            ),

            reverse=True,

        )

        best = (
            results[0]
            if results
            else None
        )

        return {

            "best_parameters": (
                best["parameters"]
                if best
                else {}
            ),

            "best_result": best,

            "total_combinations": len(
                results
            ),

            "ranking": results,

        }
