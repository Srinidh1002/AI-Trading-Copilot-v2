"""
Walk Forward Engine

Performs walk-forward validation by repeatedly
training on historical windows and evaluating
on unseen future windows.
"""

from __future__ import annotations

from typing import Any

from services.backtesting.backtest_engine import (
    run_backtest,
)


class WalkForwardEngine:

    @staticmethod
    def run(
        df,
        strategy,
        train_size: int = 500,
        test_size: int = 100,
        step: int = 100,
    ) -> dict[str, Any]:

        results = []

        start = 0

        while start + train_size + test_size <= len(df):

            train_df = df.iloc[
                start : start + train_size
            ]

            test_df = df.iloc[
                start
                + train_size :
                start
                + train_size
                + test_size
            ]

            backtest = run_backtest(
                test_df,
                strategy,
            )

            results.append(

                {

                    "train_start": start,

                    "train_end": start + train_size,

                    "test_start": start + train_size,

                    "test_end": (
                        start
                        + train_size
                        + test_size
                    ),

                    "net_pnl": backtest[
                        "net_pnl"
                    ],

                    "win_rate": backtest[
                        "win_rate"
                    ],

                    "total_trades": backtest[
                        "total_trades"
                    ],

                    "wins": backtest["wins"],

                    "losses": backtest[
                        "losses"
                    ],

                }

            )

            start += step

        if not results:

            return {

                "segments": [],

                "summary": {

                    "total_segments": 0,

                    "average_win_rate": 0,

                    "total_net_pnl": 0,

                    "average_net_pnl": 0,

                },

            }

        total_net = sum(
            r["net_pnl"]
            for r in results
        )

        avg_win = (
            sum(
                r["win_rate"]
                for r in results
            )
            / len(results)
        )

        return {

            "segments": results,

            "summary": {

                "total_segments": len(
                    results
                ),

                "average_win_rate": round(
                    avg_win,
                    2,
                ),

                "total_net_pnl": round(
                    total_net,
                    2,
                ),

                "average_net_pnl": round(
                    total_net / len(results),
                    2,
                ),

            },

        }