"""
Paper Trade Engine
"""

from services.trade.paper_trade_manager import (
    get_open_trade,
    save_trade,
    update_open_trade,
)


def process_trade(trade):

    open_trade = get_open_trade()

    if open_trade is None:

        if trade["trade_action"] == "EXECUTE":

            save_trade(trade)

        return

    update_open_trade(
        trade["current_price"]
    )