"""
Backtest Engine

Runs historical simulations on generated signals.
"""


def run_backtest(df, strategy):
    """
    Execute a basic backtest.

    Parameters
    ----------
    df : pandas.DataFrame
    strategy : callable

    Returns
    -------
    dict
    """

    trades = []
    wins = 0
    losses = 0
    total_pnl = 0.0

    for i in range(100, len(df)):

        history = df.iloc[: i + 1]

        result = strategy(history)

        if result["signal"] == "HOLD":
            continue

        entry = float(history.iloc[-1]["close"])
        exit_price = float(df.iloc[min(i + 5, len(df) - 1)]["close"])

        pnl = (
            exit_price - entry
            if result["signal"] == "BUY"
            else entry - exit_price
        )

        total_pnl += pnl

        if pnl > 0:
            wins += 1
        else:
            losses += 1

        trades.append(
            {
                "signal": result["signal"],
                "entry": entry,
                "exit": exit_price,
                "pnl": round(pnl, 2),
            }
        )

    total = wins + losses

    return {
        "trades": trades,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total) * 100, 2) if total else 0,
        "net_pnl": round(total_pnl, 2),
    }