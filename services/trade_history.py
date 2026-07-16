class TradeHistory:

    def build(
        self,
        paper_trade_result,
    ):

        if not isinstance(
            paper_trade_result,
            dict,
        ):
            return []

        return [
            paper_trade_result
        ]