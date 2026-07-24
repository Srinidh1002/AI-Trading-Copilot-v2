from services.broker.shared_client import get_market_client


class LiveLTP:

    def __init__(self):
        self.client = get_market_client()

    def get_ltp(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):

        response = self.client.get_ltp(
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            symboltoken=symboltoken,
        )

        return float(
            response["data"]["ltp"]
        )


live_ltp = LiveLTP()