from copy import deepcopy


class ActiveTradeDashboard:

    def build(
        self,
        paper_trade_result,
    ):

        if not isinstance(
            paper_trade_result,
            dict,
        ):
            return {}

        return deepcopy(
            {
                "status": paper_trade_result.get(
                    "status"
                ),
                "symbol": paper_trade_result.get(
                    "symbol"
                ),
                "entry_price": paper_trade_result.get(
                    "entry_price"
                ),
                "stop_loss": paper_trade_result.get(
                    "stop_loss"
                ),
                "target": paper_trade_result.get(
                    "target"
                ),
                "quantity": paper_trade_result.get(
                    "quantity"
                ),
                "pnl": paper_trade_result.get(
                    "pnl"
                ),
            }
        )