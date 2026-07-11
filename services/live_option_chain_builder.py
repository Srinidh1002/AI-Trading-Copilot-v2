"""
Live Angel One option-chain builder.

Builds a normalized option chain using:
- Angel One instrument master
- Nearest listed expiry
- Live FULL market data
- Actual exchange lot size

Read-only. No orders are placed.
"""

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)

from services.broker.angel_client import (
    AngelMarketDataClient,
)


class LiveOptionChainBuilder:

    def __init__(
        self,
        instrument_master=None,
        market_client=None,
    ):
        self.instrument_master = (
            instrument_master
            if instrument_master is not None
            else AngelInstrumentMaster()
        )

        self.market_client = (
            market_client
            if market_client is not None
            else AngelMarketDataClient()
        )

    @staticmethod
    def _normalize_strike(raw_strike):
        """
        Angel instrument-master strikes are commonly
        stored with a 100x multiplier.

        Example:
            2420000 -> 24200
        """

        strike = float(raw_strike)

        if strike > 100000:
            strike = strike / 100

        return strike

    @staticmethod
    def _normalize_lot_size(raw_lot_size):
        """
        Convert Angel One lot-size data into an integer.

        Angel instrument-master values may be returned
        as strings, integers, or decimal-like strings.
        """

        try:
            lot_size = int(
                float(
                    raw_lot_size
                    or 0
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            lot_size = 0

        return lot_size

    def get_nearby_contracts(
        self,
        underlying,
        spot_price,
        strikes_each_side=10,
    ):
        """
        Find CE and PE contracts around the current spot price
        for the nearest listed expiry.
        """

        if spot_price <= 0:
            raise ValueError(
                "Spot price must be greater than zero."
            )

        nearest_expiry = (
            self.instrument_master
            .get_nearest_expiry(
                underlying
            )
        )

        expiry_raw = nearest_expiry[
            "raw"
        ]

        all_contracts = (
            self.instrument_master
            .get_option_contracts(
                underlying
            )
        )

        expiry_contracts = []

        for contract in all_contracts:

            if (
                str(
                    contract.get(
                        "expiry",
                        "",
                    )
                ).strip()
                != expiry_raw
            ):
                continue

            strike = self._normalize_strike(
                contract.get(
                    "strike",
                    0,
                )
            )

            symbol = str(
                contract.get(
                    "symbol",
                    "",
                )
            ).upper()

            if symbol.endswith("CE"):
                option_type = "CE"

            elif symbol.endswith("PE"):
                option_type = "PE"

            else:
                continue

            item = dict(
                contract
            )

            item[
                "_strike"
            ] = strike

            item[
                "_option_type"
            ] = option_type

            expiry_contracts.append(
                item
            )

        available_strikes = sorted(
            {
                item["_strike"]
                for item in expiry_contracts
                if item["_strike"] > 0
            }
        )

        if not available_strikes:
            raise ValueError(
                f"No strikes found for "
                f"{underlying} {expiry_raw}."
            )

        nearest_index = min(
            range(
                len(
                    available_strikes
                )
            ),
            key=lambda index: abs(
                available_strikes[
                    index
                ]
                - spot_price
            ),
        )

        start = max(
            0,
            nearest_index
            - strikes_each_side,
        )

        end = min(
            len(
                available_strikes
            ),
            nearest_index
            + strikes_each_side
            + 1,
        )

        selected_strikes = set(
            available_strikes[
                start:end
            ]
        )

        selected_contracts = [
            item
            for item in expiry_contracts
            if item["_strike"]
            in selected_strikes
        ]

        return {
            "underlying": (
                underlying.upper()
            ),
            "expiry": nearest_expiry,
            "spot_price": spot_price,
            "contracts": (
                selected_contracts
            ),
        }

    def build_chain(
        self,
        underlying,
        spot_price,
        strikes_each_side=10,
    ):
        """
        Build a normalized live option chain.
        """

        selection = (
            self.get_nearby_contracts(
                underlying=underlying,
                spot_price=spot_price,
                strikes_each_side=(
                    strikes_each_side
                ),
            )
        )

        contracts = selection[
            "contracts"
        ]

        tokens = [
            str(
                contract.get(
                    "token"
                )
            )
            for contract in contracts
            if contract.get(
                "token"
            )
        ]

        if not tokens:
            raise ValueError(
                "No option tokens available "
                "for market-data request."
            )

        response = (
            self.market_client
            .get_market_data(
                mode="FULL",
                exchange_tokens={
                    "NFO": tokens
                },
            )
        )

        fetched = (
            response
            .get(
                "data",
                {},
            )
            .get(
                "fetched",
                [],
            )
        )

        market_by_token = {
            str(
                item.get(
                    "symbolToken",
                    "",
                )
            ): item
            for item in fetched
        }

        normalized = []

        for contract in contracts:

            token = str(
                contract.get(
                    "token",
                    "",
                )
            )

            market = (
                market_by_token.get(
                    token
                )
            )

            if not market:
                continue

            depth = (
                market.get(
                    "depth",
                    {},
                )
                or {}
            )

            buy_depth = (
                depth.get(
                    "buy",
                    [],
                )
                or []
            )

            sell_depth = (
                depth.get(
                    "sell",
                    [],
                )
                or []
            )

            bid = (
                float(
                    buy_depth[0].get(
                        "price",
                        0,
                    )
                    or 0
                )
                if buy_depth
                else 0.0
            )

            ask = (
                float(
                    sell_depth[0].get(
                        "price",
                        0,
                    )
                    or 0
                )
                if sell_depth
                else 0.0
            )

            lot_size = (
                self._normalize_lot_size(
                    contract.get(
                        "lotsize",
                        0,
                    )
                )
            )

            normalized.append({
                "token": token,
                "symbol": contract.get(
                    "symbol"
                ),
                "strike": contract[
                    "_strike"
                ],
                "option_type": contract[
                    "_option_type"
                ],
                "expiry": selection[
                    "expiry"
                ]["display"],
                "lot_size": lot_size,
                "premium": float(
                    market.get(
                        "ltp",
                        0,
                    )
                    or 0
                ),
                "bid": bid,
                "ask": ask,
                "volume": int(
                    market.get(
                        "tradeVolume",
                        0,
                    )
                    or 0
                ),
                "open_interest": int(
                    market.get(
                        "opnInterest",
                        0,
                    )
                    or 0
                ),

                # Greeks are optional until
                # we calculate them locally.
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "iv": None,
            })

        return {
            "underlying": selection[
                "underlying"
            ],
            "spot_price": spot_price,
            "expiry": selection[
                "expiry"
            ]["display"],
            "contracts": normalized,
            "requested_contracts": len(
                contracts
            ),
            "received_contracts": len(
                normalized
            ),
        }