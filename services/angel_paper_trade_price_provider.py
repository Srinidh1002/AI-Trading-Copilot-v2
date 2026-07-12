"""
Angel One live price provider for paper-trade positions.

Responsibilities:
- Accept one paper-trade dictionary.
- Extract and validate the option symbol token.
- Resolve the market-data exchange.
- Request the current LTP from AngelMarketDataClient.
- Validate the broker response.
- Return one positive finite option price.

IMPORTANT:
- Market-data access only.
- No order placement.
- No real trade execution.
"""

import math


class AngelPaperTradePriceProvider:

    def __init__(
        self,
        market_data_client,
        default_option_exchange="NFO",
    ):
        if market_data_client is None:
            raise ValueError(
                "market_data_client is required."
            )

        if not hasattr(
            market_data_client,
            "get_market_data",
        ):
            raise ValueError(
                "market_data_client must provide "
                "get_market_data()."
            )

        if not isinstance(
            default_option_exchange,
            str,
        ):
            raise ValueError(
                "default_option_exchange must be a string."
            )

        default_option_exchange = (
            default_option_exchange.strip().upper()
        )

        if not default_option_exchange:
            raise ValueError(
                "default_option_exchange cannot be empty."
            )

        self.market_data_client = (
            market_data_client
        )

        self.default_option_exchange = (
            default_option_exchange
        )

    # ---------------------------------------------------------
    # TOKEN
    # ---------------------------------------------------------

    @staticmethod
    def _get_symboltoken(
        trade,
    ):
        if not isinstance(
            trade,
            dict,
        ):
            raise ValueError(
                "Paper trade must be a dictionary."
            )

        symboltoken = trade.get(
            "symboltoken"
        )

        if symboltoken is None:
            raise ValueError(
                "Paper trade does not contain symboltoken."
            )

        symboltoken = str(
            symboltoken
        ).strip()

        if not symboltoken:
            raise ValueError(
                "Paper trade symboltoken cannot be empty."
            )

        return symboltoken

    # ---------------------------------------------------------
    # EXCHANGE
    # ---------------------------------------------------------

    def _get_market_data_exchange(
        self,
        trade,
    ):
        """
        Resolve the exchange used for the option LTP request.

        Priority:
        1. metadata.market_data_exchange
        2. metadata.option_exchange
        3. default_option_exchange

        The top-level trade.exchange may describe the underlying
        exchange, so it is deliberately not used automatically
        for an option-contract LTP request.
        """

        metadata = trade.get(
            "metadata",
            {},
        )

        if metadata is None:
            metadata = {}

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValueError(
                "Paper trade metadata must be a dictionary."
            )

        exchange = (
            metadata.get(
                "market_data_exchange"
            )
            or metadata.get(
                "option_exchange"
            )
            or self.default_option_exchange
        )

        if not isinstance(
            exchange,
            str,
        ):
            raise ValueError(
                "Option market-data exchange must be a string."
            )

        exchange = (
            exchange.strip().upper()
        )

        if not exchange:
            raise ValueError(
                "Option market-data exchange cannot be empty."
            )

        return exchange

    # ---------------------------------------------------------
    # PRICE VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_price(
        price,
    ):
        if isinstance(
            price,
            bool,
        ):
            raise ValueError(
                "Broker LTP must be numeric, not boolean."
            )

        try:
            price = float(
                price
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Broker LTP must be numeric."
            ) from exc

        if not math.isfinite(
            price
        ):
            raise ValueError(
                "Broker LTP must be finite."
            )

        if price <= 0:
            raise ValueError(
                "Broker LTP must be greater than zero."
            )

        return price

    # ---------------------------------------------------------
    # RESPONSE EXTRACTION
    # ---------------------------------------------------------

    @classmethod
    def _extract_ltp(
        cls,
        response,
    ):
        if not isinstance(
            response,
            dict,
        ):
            raise ValueError(
                "Broker market-data response must be a dictionary."
            )

        data = response.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Broker response does not contain valid data."
            )

        fetched = data.get(
            "fetched"
        )

        if not isinstance(
            fetched,
            list,
        ):
            raise ValueError(
                "Broker response does not contain a valid fetched list."
            )

        if not fetched:
            raise ValueError(
                "Broker returned no fetched market-data records."
            )

        first_record = fetched[0]

        if not isinstance(
            first_record,
            dict,
        ):
            raise ValueError(
                "Broker fetched record must be a dictionary."
            )

        if "ltp" not in first_record:
            raise ValueError(
                "Broker fetched record does not contain ltp."
            )

        return cls._validate_price(
            first_record.get(
                "ltp"
            )
        )

    # ---------------------------------------------------------
    # FETCH PRICE
    # ---------------------------------------------------------

    def get_price(
        self,
        trade,
    ):
        symboltoken = (
            self._get_symboltoken(
                trade
            )
        )

        exchange = (
            self._get_market_data_exchange(
                trade
            )
        )

        response = (
            self.market_data_client.get_market_data(
                mode="LTP",
                exchange_tokens={
                    exchange: [
                        symboltoken
                    ]
                },
            )
        )

        return self._extract_ltp(
            response
        )

    # ---------------------------------------------------------
    # CALLABLE INTERFACE
    # ---------------------------------------------------------

    def __call__(
        self,
        trade,
    ):
        return self.get_price(
            trade
        )