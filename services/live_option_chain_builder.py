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

from collections.abc import Mapping
from datetime import datetime, timezone
import math

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)

from services.broker.shared_client import (
    get_market_client,
)

from services.option_chain_validator import (
    validate_option_chain,
)

from services.option_full_response_validator import (
    validate_option_full_response_partial,
)
from services.options.angel_option_provider_capabilities import (
    angel_option_provider_capabilities,
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
            option_cache=None,
            clock=None,
            maximum_quote_age_seconds=300.0,
            maximum_future_skew_seconds=5.0,
        ):
            self.instrument_master = (
                instrument_master
                if instrument_master is not None
                else AngelInstrumentMaster()
            )

            self.market_client = (
                market_client
                if market_client is not None
                else get_market_client()
            )

            self.option_cache = option_cache

            self.clock = (
                clock
                if clock is not None
                else lambda: datetime.now(timezone.utc)
            )

            if not callable(self.clock):
                raise TypeError("clock must be callable")

            self.maximum_quote_age_seconds = float(
                maximum_quote_age_seconds
            )
            self.maximum_future_skew_seconds = float(
                maximum_future_skew_seconds
            )

            if self.maximum_quote_age_seconds < 0:
                raise ValueError(
                    "maximum_quote_age_seconds cannot be negative"
                )

            if self.maximum_future_skew_seconds < 0:
                raise ValueError(
                    "maximum_future_skew_seconds cannot be negative"
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

    @staticmethod
    def _greek_number(value, field_name, *, signed=False):
        """Return a finite provider Greek, or reject the provider row.

        Greek values are enrichment only.  They must never be coerced to a
        synthetic zero because zero would be indistinguishable from live
        provider evidence downstream.
        """
        if isinstance(value, bool):
            raise ValueError(field_name)
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(field_name) from exc
        if not math.isfinite(result) or (not signed and result < 0):
            raise ValueError(field_name)
        return result

    @staticmethod
    def _greek_option_type(value):
        result = str(value or "").strip().upper()
        if result == "CALL":
            result = "CE"
        elif result == "PUT":
            result = "PE"
        if result not in {"CE", "PE"}:
            raise ValueError("optionType")
        return result

    @staticmethod
    def _greek_strike(value):
        if isinstance(value, bool):
            raise ValueError("strikePrice")
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("strikePrice") from exc
        if not math.isfinite(result) or result <= 0:
            raise ValueError("strikePrice")
        return result

    def _capture_greek_rows(
        self,
        *,
        underlying,
        option_exchange,
        expiry,
    ):
        """Read one nearest-expiry Greek capture from this builder's client.

        This deliberately uses ``self.market_client`` rather than constructing
        ``AngelOptionClient``: certification injects its shared client here,
        preserving the one process-wide Angel request controller/session
        authority.  ``AngelMarketDataClient`` also caches this exact request
        key, preventing duplicate requests by concurrent/reused captures.
        """
        capability = angel_option_provider_capabilities(
            underlying,
            option_exchange,
        )
        if not capability.option_greeks_supported:
            return (), {
                "state": "UNSUPPORTED_BY_PROVIDER",
                "reason": "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE",
            }
        try:
            response = self.market_client.get_option_greeks(
                capability.underlying_symbol,
                expiry,
            )
        except Exception as exc:
            return (), {
                "state": "PROVIDER_FAILURE",
                "reason": "OPTION_GREEKS_PROVIDER_FAILURE_"
                + type(exc).__name__.upper(),
            }
        if not isinstance(response, Mapping):
            return (), {
                "state": "DATA_UNAVAILABLE",
                "reason": "OPTION_GREEKS_DATA_UNAVAILABLE",
            }
        rows = response.get("data")
        if not isinstance(rows, list) or not rows:
            return (), {
                "state": "DATA_UNAVAILABLE",
                "reason": "OPTION_GREEKS_DATA_UNAVAILABLE",
            }
        if not all(isinstance(row, Mapping) for row in rows):
            return (), {
                "state": "DATA_MALFORMED",
                "reason": "OPTION_GREEKS_DATA_MALFORMED",
            }
        return tuple(rows), {"state": "SUPPORTED", "reason": None}

    def _enrich_with_greeks(
        self,
        *,
        contracts,
        greek_rows,
        greek_capture,
        expiry,
    ):
        """Strictly join provider Greeks without modifying FULL quote fields.

        Angel's Greek payload is scoped to the exact requested expiry.  Rows
        identify a contract by provider token when supplied, otherwise by
        provider trading symbol, otherwise by the exact
        (requested-expiry, strikePrice, optionType) tuple.  There is no
        positional or nearest-strike matching.
        """
        if greek_capture["state"] != "SUPPORTED":
            return contracts, greek_capture

        by_token = {str(item["token"]): item for item in contracts}
        by_symbol = {str(item["symbol"]).strip().upper(): item for item in contracts}
        by_strike_type = {
            (float(item["strike"]), str(item["option_type"]).upper()): item
            for item in contracts
        }
        matches = {}
        try:
            for row in greek_rows:
                token = str(row.get("symbolToken", row.get("symboltoken", row.get("token", "")))).strip()
                symbol = str(row.get("tradingSymbol", row.get("tradingsymbol", row.get("symbol", "")))).strip().upper()
                strike = self._greek_strike(row.get("strikePrice", row.get("strike")))
                option_type = self._greek_option_type(row.get("optionType", row.get("option_type")))
                candidate = by_token.get(token) if token else None
                if not token and symbol:
                    candidate = by_symbol.get(symbol)
                if candidate is None and not token and not symbol:
                    candidate = by_strike_type.get((strike, option_type))
                if candidate is None:
                    continue
                # Any supplied secondary identity must corroborate the match.
                if (token and token != candidate["token"]) or (symbol and symbol != str(candidate["symbol"]).strip().upper()):
                    continue
                if (strike, option_type) != (float(candidate["strike"]), str(candidate["option_type"]).upper()):
                    continue
                values = {
                    "delta": self._greek_number(row.get("delta"), "delta", signed=True),
                    "gamma": self._greek_number(row.get("gamma"), "gamma"),
                    "theta": self._greek_number(row.get("theta"), "theta", signed=True),
                    "vega": self._greek_number(row.get("vega"), "vega"),
                    "iv": self._greek_number(row.get("impliedVolatility", row.get("iv")), "impliedVolatility"),
                }
                key = candidate["token"]
                # Ambiguous duplicate Greek identities fail closed for that
                # contract; no provider row wins by array order.
                if key in matches:
                    matches[key] = None
                else:
                    matches[key] = values
        except ValueError:
            return contracts, {
                "state": "DATA_MALFORMED",
                "reason": "OPTION_GREEKS_DATA_MALFORMED",
            }

        enriched = []
        for contract in contracts:
            values = matches.get(contract["token"])
            enriched.append({**contract, **values} if values is not None else contract)
        return enriched, {
            "state": "SUPPORTED" if any(value is not None for value in matches.values()) else "DATA_UNAVAILABLE",
            "reason": None if any(value is not None for value in matches.values()) else "OPTION_GREEKS_NO_EXACT_MATCH",
        }

    def get_nearby_contracts(
        self,
        underlying,
        spot_price,
        strikes_each_side=10,
        option_exchange="NFO",
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
                underlying,
                exchange=option_exchange,
            )
        )

        expiry_raw = nearest_expiry[
            "raw"
        ]

        all_contracts = (
            self.instrument_master
            .get_option_contracts(
                underlying,
                exchange=option_exchange,
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
        option_exchange="NFO",
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
                option_exchange=option_exchange,
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

        current_time = self.clock()

        # 1. Initialize an in-memory TTL cache on the builder instance if missing
        if not hasattr(self, "_ttl_cache"):
              self._ttl_cache = {}
              self._ttl_seconds = 60.0

        # 2. Use the exact tuple of required option tokens as the cache key
        cache_key = tuple(sorted(tokens))
        cached = self._ttl_cache.get(cache_key)

        # 3. Serve from RAM if we queried these exact strikes less than 60s ago
        if cached and (current_time - cached["received_at"]).total_seconds() < self._ttl_seconds:
              response = cached["response"]
              received_at = cached["received_at"]
        else:
              # 4. Otherwise, fetch fresh data from Angel One
              response = (
                  self.market_client
                  .get_market_data(
                      mode="FULL",
                      exchange_tokens={
                          option_exchange: tokens
                      },
                  )
              )
              received_at = current_time
              
              # 5. Save to the local instance cache
              self._ttl_cache[cache_key] = {
                  "response": response,
                  "received_at": received_at
              }

        if (
              not isinstance(received_at, datetime)
              or received_at.tzinfo is None
          ):
              raise ValueError(
                  "option quote receipt timestamp "
                  "must be timezone-aware"
              )

        full_validation = (
            validate_option_full_response_partial(
                response=response,
                option_exchange=option_exchange,
                requested_tokens=tokens,
                received_at=received_at,
                maximum_quote_age_seconds=(
                    self.maximum_quote_age_seconds
                ),
                maximum_future_skew_seconds=(
                    self.maximum_future_skew_seconds
                ),
            )
        )

        chain_evidence_validation = (
            validate_option_full_response_partial(
                response=response,
                option_exchange=option_exchange,
                requested_tokens=tokens,
                received_at=received_at,
                maximum_quote_age_seconds=(
                    self.maximum_quote_age_seconds
                ),
                maximum_future_skew_seconds=(
                    self.maximum_future_skew_seconds
                ),
                allow_zero_market_prices=True,
            )
        )

        market_by_token = (
            full_validation.validated_by_token
        )

        chain_evidence_market_by_token = (
            chain_evidence_validation.validated_by_token
        )

        # ---------------------------------
        # NORMALIZE CONTRACTS
        # ---------------------------------

        normalized = []
        chain_evidence_normalized = []

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

            bid = market[
                "_validated_bid"
            ]

            # ---------------------------------
            # BEST ASK
            # ---------------------------------

            ask = market[
                "_validated_ask"
            ]

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
                    market[
                        "_validated_ltp"
                    ]
                ),

                "bid": (
                    bid
                ),

                "ask": (
                    ask
                ),

                "volume": (
                    market[
                        "_validated_volume"
                    ]
                ),

                "open_interest": (
                    market[
                        "_validated_open_interest"
                    ]
                ),

                "provider_timestamp": (
                    market[
                        "_validated_provider_timestamp"
                    ]
                ),

                "provider_timestamp_field": (
                    market[
                        "_validated_provider_timestamp_field"
                    ]
                ),

                "provider_timestamp_age_seconds": (
                    market[
                        "_validated_provider_timestamp_age_seconds"
                    ]
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
                chain_evidence_market_by_token.get(
                    token
                )
            )

            if not market:
                continue

            lot_size = (
                self._normalize_lot_size(
                    contract.get(
                        "lotsize",
                        0,
                    )
                )
            )

            chain_evidence_normalized.append({
                "token": token,
                "symbol": contract.get("symbol"),
                "strike": contract["_strike"],
                "option_type": contract["_option_type"],
                "expiry": selection["expiry"]["display"],
                "lot_size": lot_size,
                "premium": market["_validated_ltp"],
                "bid": market["_validated_bid"],
                "ask": market["_validated_ask"],
                "volume": market["_validated_volume"],
                "open_interest": market["_validated_open_interest"],
                "provider_timestamp": (
                    market["_validated_provider_timestamp"]
                ),
                "provider_timestamp_field": (
                    market["_validated_provider_timestamp_field"]
                ),
                "provider_timestamp_age_seconds": (
                    market["_validated_provider_timestamp_age_seconds"]
                ),
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "iv": None,
            })

        if not normalized:
            raise RuntimeError(
                "No live option contracts could be "
                "normalized from broker data."
            )

        # ---------------------------------
        # MANDATORY OPTION-CHAIN
        # INTEGRITY VALIDATION
        # ---------------------------------

        greek_rows, greek_capture = self._capture_greek_rows(
            underlying=selection["underlying"],
            option_exchange=option_exchange,
            expiry=selection["expiry"]["display"],
        )
        normalized, greek_capture = self._enrich_with_greeks(
            contracts=normalized,
            greek_rows=greek_rows,
            greek_capture=greek_capture,
            expiry=selection["expiry"]["display"],
        )

        validated_contracts = (
            validate_option_chain(
                normalized
            )
        )

        provider_timestamps = tuple(
            item["provider_timestamp"]
            for item in normalized
        )

        if any(
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
            for value in provider_timestamps
        ):
            raise RuntimeError(
                "Validated option FULL capture "
                "contains invalid provider timestamps."
            )

        requested_contract_count = len(
            tokens
        )
        received_contract_count = len(
            normalized
        )
        validated_contract_count = len(
            validated_contracts
        )

        downstream_malformed_contract_count = (
            received_contract_count
            - validated_contract_count
        )

        unfetched_contract_count = (
            full_validation.unfetched_contract_count
        )

        malformed_contract_count = (
            full_validation.malformed_contract_count
            + downstream_malformed_contract_count
        )

        if (
            requested_contract_count <= 0
            or received_contract_count < 0
            or validated_contract_count < 0
            or downstream_malformed_contract_count < 0
            or unfetched_contract_count < 0
            or malformed_contract_count < 0
            or (
                validated_contract_count
                + unfetched_contract_count
                + malformed_contract_count
                != requested_contract_count
            )
        ):
            raise RuntimeError(
                "Option FULL capture accounting "
                "is inconsistent."
            )

        full_capture = {
            "requested_contract_count": (
                requested_contract_count
            ),
            "fetched_contract_count": (
                validated_contract_count
            ),
            "unfetched_contract_count": (
                unfetched_contract_count
            ),
            "malformed_contract_count": (
                malformed_contract_count
            ),
            "oldest_provider_timestamp": (
                min(provider_timestamps)
                if validated_contract_count > 0
                else None
            ),
            "newest_provider_timestamp": (
                max(provider_timestamps)
                if validated_contract_count > 0
                else None
            ),
            "exchange_identity_verified": True,
        }

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

            "chain_evidence_contracts": (
                chain_evidence_normalized
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

            # Sanitized provider-capability evidence. No raw provider
            # response, credentials, or additional acquisition is retained.
            "full_capture": full_capture,

            # Sanitized capture evidence only.  Raw provider payloads and
            # credentials are never retained in the certified capture.
            "greek_capture": greek_capture,
        }
