"""
Live Angel One option-chain builder.

Builds a normalized and integrity-validated option chain using:
- Angel One instrument master
- Nearest listed expiry
- Live FULL market data
- Actual exchange lot size
- Mandatory option-chain integrity validation

Read-only. No orders are placed.
"""

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.option_chain_validator import (
    validate_option_chain,
)


class LiveOptionChainBuilder:
    """
    Build a live option chain from Angel One data.

    Flow:
    1. Find the nearest listed expiry.
    2. Find nearby CE and PE contracts.
    3. Fetch live FULL market data.
    4. Normalize broker and instrument-master data.
    5. Validate the complete normalized option chain.
    6. Return only integrity-validated contracts.

    Read-only.
    No orders are placed.
    """

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
    def _normalize_strike(
        raw_strike,
    ):
        """
        Normalize Angel One instrument-master strike.

        Angel instrument-master strikes are commonly
        stored with a 100x multiplier.

        Example:
            2420000 -> 24200
        """

        try:
            strike = float(
                raw_strike
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        if strike > 100000:
            strike = (
                strike / 100
            )

        return strike

    @staticmethod
    def _normalize_lot_size(
        raw_lot_size,
    ):
        """
        Convert Angel One lot-size data into an integer.

        Instrument-master values may be returned as:
        - strings
        - integers
        - decimal-like strings
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

    @staticmethod
    def _safe_float(
        value,
        default=0.0,
    ):
        """
        Safely convert broker data to float.

        Invalid broker values are normalized to the
        supplied default and will later be handled by
        the mandatory option-chain validator.
        """

        try:
            return float(
                value
                or default
            )

        except (
            TypeError,
            ValueError,
        ):
            return float(
                default
            )

    @staticmethod
    def _safe_int(
        value,
        default=0,
    ):
        """
        Safely convert broker data to integer.

        Invalid broker values are normalized to the
        supplied default and will later be handled by
        the mandatory option-chain validator.
        """

        try:
            return int(
                float(
                    value
                    or default
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            return int(
                default
            )

    def get_nearby_contracts(
        self,
        underlying,
        spot_price,
        strikes_each_side=10,
    ):
        """
        Find CE and PE contracts around the current
        spot price for the nearest listed expiry.
        """

        if spot_price <= 0:
            raise ValueError(
                "Spot price must be greater than zero."
            )

        if strikes_each_side < 0:
            raise ValueError(
                "strikes_each_side cannot be negative."
            )

        underlying = str(
            underlying
        ).strip().upper()

        if not underlying:
            raise ValueError(
                "Underlying is required."
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

            if not isinstance(
                contract,
                dict,
            ):
                continue

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

            strike = (
                self._normalize_strike(
                    contract.get(
                        "strike",
                        0,
                    )
                )
            )

            if strike <= 0:
                continue

            symbol = str(
                contract.get(
                    "symbol",
                    "",
                )
            ).strip().upper()

            if symbol.endswith(
                "CE"
            ):
                option_type = (
                    "CE"
                )

            elif symbol.endswith(
                "PE"
            ):
                option_type = (
                    "PE"
                )

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
                item[
                    "_strike"
                ]
                for item
                in expiry_contracts
                if item[
                    "_strike"
                ] > 0
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
            for item
            in expiry_contracts
            if item[
                "_strike"
            ]
            in selected_strikes
        ]

        if not selected_contracts:
            raise ValueError(
                "No nearby option contracts "
                "were selected."
            )

        return {
            "underlying": underlying,
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
        Build a normalized and integrity-validated
        live option chain.

        Invalid individual contracts are removed by
        validate_option_chain().

        Duplicate contracts are removed.

        If no valid contracts remain, the validator
        fails closed and the chain is not returned.
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

        # ---------------------------------
        # COLLECT OPTION TOKENS
        # ---------------------------------

        tokens = []

        seen_tokens = set()

        for contract in contracts:

            raw_token = contract.get(
                "token"
            )

            if raw_token is None:
                continue

            token = str(
                raw_token
            ).strip()

            if not token:
                continue

            if token in seen_tokens:
                continue

            seen_tokens.add(
                token
            )

            tokens.append(
                token
            )

        if not tokens:
            raise ValueError(
                "No option tokens available "
                "for market-data request."
            )

        # ---------------------------------
        # FETCH LIVE FULL MARKET DATA
        # ---------------------------------

        response = (
            self.market_client
            .get_market_data(
                mode="FULL",
                exchange_tokens={
                    "NFO": tokens
                },
            )
        )

        if not response:
            raise RuntimeError(
                "No option market-data response "
                "was received."
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
            or []
        )

        if not fetched:
            raise RuntimeError(
                "No live option contracts were "
                "received from the broker."
            )

        # ---------------------------------
        # INDEX MARKET DATA BY TOKEN
        # ---------------------------------

        market_by_token = {}

        for item in fetched:

            if not isinstance(
                item,
                dict,
            ):
                continue

            token = str(
                item.get(
                    "symbolToken",
                    "",
                )
            ).strip()

            if not token:
                continue

            market_by_token[
                token
            ] = item

        # ---------------------------------
        # NORMALIZE CONTRACTS
        # ---------------------------------

        normalized = []

        for contract in contracts:

            token = str(
                contract.get(
                    "token",
                    "",
                )
            ).strip()

            if not token:
                continue

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

            # ---------------------------------
            # BEST BID
            # ---------------------------------

            bid = 0.0

            if (
                buy_depth
                and isinstance(
                    buy_depth[0],
                    dict,
                )
            ):
                bid = (
                    self._safe_float(
                        buy_depth[
                            0
                        ].get(
                            "price",
                            0,
                        )
                    )
                )

            # ---------------------------------
            # BEST ASK
            # ---------------------------------

            ask = 0.0

            if (
                sell_depth
                and isinstance(
                    sell_depth[0],
                    dict,
                )
            ):
                ask = (
                    self._safe_float(
                        sell_depth[
                            0
                        ].get(
                            "price",
                            0,
                        )
                    )
                )

            lot_size = (
                self._normalize_lot_size(
                    contract.get(
                        "lotsize",
                        0,
                    )
                )
            )

            normalized_contract = {
                "token": token,

                "symbol": (
                    contract.get(
                        "symbol"
                    )
                ),

                "strike": (
                    contract[
                        "_strike"
                    ]
                ),

                "option_type": (
                    contract[
                        "_option_type"
                    ]
                ),

                "expiry": (
                    selection[
                        "expiry"
                    ][
                        "display"
                    ]
                ),

                "lot_size": (
                    lot_size
                ),

                "premium": (
                    self._safe_float(
                        market.get(
                            "ltp",
                            0,
                        )
                    )
                ),

                "bid": (
                    bid
                ),

                "ask": (
                    ask
                ),

                "volume": (
                    self._safe_int(
                        market.get(
                            "tradeVolume",
                            0,
                        )
                    )
                ),

                "open_interest": (
                    self._safe_int(
                        market.get(
                            "opnInterest",
                            0,
                        )
                    )
                ),

                # Greeks remain optional until
                # supplied by a Greeks service.
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "iv": None,
            }

            normalized.append(
                normalized_contract
            )

        if not normalized:
            raise RuntimeError(
                "No option contracts could be "
                "normalized from live broker data."
            )

        # ---------------------------------
        # MANDATORY OPTION-CHAIN
        # INTEGRITY VALIDATION
        # ---------------------------------

        validated_contracts = (
            validate_option_chain(
                normalized
            )
        )

        # ---------------------------------
        # RETURN VALIDATED CHAIN ONLY
        # ---------------------------------

        return {
            "underlying": (
                selection[
                    "underlying"
                ]
            ),

            "spot_price": (
                spot_price
            ),

            "expiry": (
                selection[
                    "expiry"
                ][
                    "display"
                ]
            ),

            "contracts": (
                validated_contracts
            ),

            "requested_contracts": (
                len(
                    contracts
                )
            ),

            "received_contracts": (
                len(
                    normalized
                )
            ),

            "validated_contracts": (
                len(
                    validated_contracts
                )
            ),

            "rejected_contracts": (
                len(
                    normalized
                )
                - len(
                    validated_contracts
                )
            ),

            "integrity_validated": True,
        }