class DailyPerformanceSummary:

    def build(
        self,
        paper_trade_result,
    ):

        if not isinstance(
            paper_trade_result,
            dict,
        ):
            return {}

        return {
            "status": paper_trade_result.get(
                "status"
            ),
            "pnl": paper_trade_result.get(
                "pnl"
            ),
            "symbol": paper_trade_result.get(
                "symbol"
            ),
        }