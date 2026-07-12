"""
Safety-gated live option decision pipeline.

Flow:
1. Validate live spot-price integrity.
2. Optionally validate the live Indian market session,
   including configured NSE trading holidays.
3. Analyse the underlying market.
4. Detect and confirm valid trading setups.
5. Build the live option chain only after authorization.
6. Select the best CE or PE contract.
7. Build a risk-controlled trade plan when capital is supplied.
8. Attach a structured decision audit trail.

Read-only. No orders are placed.
"""

from services.live_analysis_pipeline import (
    LiveAnalysisPipeline,
)

from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)

from services.option_contract_selector import (
    select_option_contract,
)

from services.setup_trigger_engine import (
    evaluate_setup_trigger,
)

from services.breakout_confirmation_engine import (
    confirm_breakout,
)

from services.completed_candle_service import (
    CompletedCandleService,
)

from services.market_session_guard import (
    evaluate_market_session,
)

from services.market_data_validator import (
    validate_candle,
    validate_live_price,
)

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.trade_plan_engine import (
    build_trade_plan,
)

from services.decision_audit_trail import (
    DecisionAuditTrail,
)

from services.decision_audit_logger import (
    DecisionAuditLogger,
)


class LiveOptionDecisionPipeline:
    """
    Complete safety-gated live option decision pipeline.

    Includes:
    - Spot-price integrity validation
    - NSE holiday validation
    - Market-session validation
    - Market analysis
    - Setup detection
    - Completed-candle validation
    - Breakout/breakdown confirmation
    - Candle-freshness validation
    - Option-chain construction
    - Contract selection
    - Risk planning
    - Decision audit trail
    """

    def __init__(
        self,
        analysis_pipeline=None,
        option_chain_builder=None,
        completed_candle_service=None,
        holiday_calendar=None,
        audit_logger=None,
        persist_audit=False,
    ):
        self.analysis_pipeline = (
            analysis_pipeline
            if analysis_pipeline is not None
            else LiveAnalysisPipeline()
        )

        self.option_chain_builder = (
            option_chain_builder
            if option_chain_builder is not None
            else LiveOptionChainBuilder()
        )

        self.completed_candle_service = (
            completed_candle_service
            if completed_candle_service is not None
            else CompletedCandleService(
                market_client=(
                    AngelMarketDataClient()
                )
            )
        )

        self.holiday_calendar = (
            holiday_calendar
            if holiday_calendar is not None
            else get_nse_holiday_calendar()
        )

        self.persist_audit = bool(
            persist_audit
        )

        self.audit_logger = (
            audit_logger
            if audit_logger is not None
            else (
                DecisionAuditLogger()
                if self.persist_audit
                else None
            )
        )

    @staticmethod
    def _no_contract(
        reason,
        option_type=None,
    ):
        """
        Return a consistent unselected contract result.
        """

        return {
            "selected": False,
            "decision": "NO_CONTRACT",
            "symbol": None,
            "strike": None,
            "option_type": option_type,
            "expiry": None,
            "premium": None,
            "lot_size": 0,
            "score": 0,
            "reasons": [
                reason
            ],
        }

    @staticmethod
    def _extract_market_inputs(
        market_result,
    ):
        """
        Extract ATR, support, and resistance.
        """

        technical = market_result.get(
            "technical",
            {},
        ) or {}

        indicators = technical.get(
            "indicators",
            {},
        ) or {}

        atr = float(
            indicators.get(
                "atr",
                0,
            )
            or 0
        )

        candlestick = market_result.get(
            "candlestick",
            {},
        ) or {}

        support = candlestick.get(
            "support"
        )

        resistance = candlestick.get(
            "resistance"
        )

        return {
            "atr": atr,
            "support": support,
            "resistance": resistance,
        }

    @staticmethod
    def _extract_chart_analysis(
        market_result,
    ):
        """
        Extract chart-pattern analysis while supporting
        common result-key names.
        """

        return (
            market_result.get(
                "chart",
                {},
            )
            or market_result.get(
                "chart_patterns",
                {},
            )
            or market_result.get(
                "chart_pattern",
                {},
            )
            or {}
        )

    def analyse(
        self,
        exchange,
        symboltoken,
        underlying,
        spot_price,
        strikes_each_side=5,
        end_time=None,
        capital=None,
        risk_percent=1.0,
        minimum_risk_reward=2.0,
        maximum_capital_usage_percent=100.0,
        option_stop_percent=20.0,
        atr_stop_multiplier=1.0,
        breakout_buffer_percent=0.0,
        confirmation_interval="FIVE_MINUTE",
        enforce_market_session=False,
        session_now=None,
        maximum_candle_age_minutes=10,
    ):
        """
        Run the complete pipeline and attach a structured
        decision audit trail.

        Existing pipeline decisions and exception behavior
        remain unchanged.
        """

        result = self._analyse_core(
            exchange=exchange,
            symboltoken=symboltoken,
            underlying=underlying,
            spot_price=spot_price,
            strikes_each_side=strikes_each_side,
            end_time=end_time,
            capital=capital,
            risk_percent=risk_percent,
            minimum_risk_reward=(
                minimum_risk_reward
            ),
            maximum_capital_usage_percent=(
                maximum_capital_usage_percent
            ),
            option_stop_percent=(
                option_stop_percent
            ),
            atr_stop_multiplier=(
                atr_stop_multiplier
            ),
            breakout_buffer_percent=(
                breakout_buffer_percent
            ),
            confirmation_interval=(
                confirmation_interval
            ),
            enforce_market_session=(
                enforce_market_session
            ),
            session_now=session_now,
            maximum_candle_age_minutes=(
                maximum_candle_age_minutes
            ),
        )

        audit = DecisionAuditTrail()

        # ---------------------------------
        # MARKET SESSION AUDIT
        # ---------------------------------

        session_status = (
            result.get(
                "session_status"
            )
            or result.get(
                "market_session"
            )
        )

        if session_status:

            market_open = bool(
                session_status.get(
                    "market_open",
                    False,
                )
            )

            session_allowed = bool(
                session_status.get(
                    "allowed",
                    market_open,
                )
            )

            audit.record(
                stage="MARKET_SESSION",
                status=(
                    "PASSED"
                    if session_allowed
                    else "BLOCKED"
                ),
                decision=(
                    session_status.get(
                        "status"
                    )
                ),
                reasons=(
                    session_status.get(
                        "reasons",
                        [],
                    )
                ),
                details={
                    "market_open": market_open,
                    "allowed": session_allowed,
                    "is_weekday": (
                        session_status.get(
                            "is_weekday"
                        )
                    ),
                    "is_market_holiday": (
                        session_status.get(
                            "is_market_holiday"
                        )
                    ),
                    "within_market_hours": (
                        session_status.get(
                            "within_market_hours"
                        )
                    ),
                    "candle_fresh": (
                        session_status.get(
                            "candle_fresh"
                        )
                    ),
                },
            )

        # ---------------------------------
        # MARKET ANALYSIS AUDIT
        # ---------------------------------

        market_analysis = result.get(
            "market_analysis"
        )

        if market_analysis is not None:

            audit.record(
                stage="MARKET_ANALYSIS",
                status="COMPLETED",
                decision=(
                    result.get(
                        "market_decision"
                    )
                ),
                details={
                    "direction": (
                        result.get(
                            "direction"
                        )
                    ),
                },
            )

        # ---------------------------------
        # SETUP TRIGGER AUDIT
        # ---------------------------------

        setup_trigger = result.get(
            "setup_trigger"
        )

        if setup_trigger is not None:

            setup_status = str(
                setup_trigger.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            audit.record(
                stage="SETUP_TRIGGER",
                status=(
                    "WAITING"
                    if setup_status.startswith(
                        "WAITING"
                    )
                    else "COMPLETED"
                ),
                decision=setup_status,
                reasons=(
                    setup_trigger.get(
                        "reasons",
                        [],
                    )
                ),
                details={
                    "direction": (
                        setup_trigger.get(
                            "direction"
                        )
                    ),
                    "trigger_price": (
                        setup_trigger.get(
                            "trigger_price"
                        )
                    ),
                },
            )

        # ---------------------------------
        # COMPLETED CANDLE AUDIT
        # ---------------------------------

        completed_candle = result.get(
            "completed_candle"
        )

        if completed_candle is not None:

            audit.record(
                stage="COMPLETED_CANDLE",
                status="PASSED",
                decision="VALIDATED",
                details={
                    "timestamp": (
                        completed_candle.get(
                            "timestamp"
                        )
                    ),
                    "close": (
                        completed_candle.get(
                            "close"
                        )
                    ),
                },
            )

        # ---------------------------------
        # BREAKOUT CONFIRMATION AUDIT
        # ---------------------------------

        breakout_confirmation = result.get(
            "breakout_confirmation"
        )

        if breakout_confirmation is not None:

            confirmed = bool(
                breakout_confirmation.get(
                    "confirmed",
                    False,
                )
            )

            audit.record(
                stage="BREAKOUT_CONFIRMATION",
                status=(
                    "PASSED"
                    if confirmed
                    else "WAITING"
                ),
                decision=(
                    breakout_confirmation.get(
                        "status"
                    )
                ),
                reasons=(
                    breakout_confirmation.get(
                        "reasons",
                        [],
                    )
                ),
                details={
                    "confirmed": confirmed,
                    "direction": (
                        breakout_confirmation.get(
                            "direction"
                        )
                    ),
                    "trigger_price": (
                        breakout_confirmation.get(
                            "trigger_price"
                        )
                    ),
                },
            )

        # ---------------------------------
        # OPTION CHAIN AUDIT
        # ---------------------------------

        option_chain = result.get(
            "option_chain"
        )

        if option_chain is not None:

            contracts = (
                option_chain.get(
                    "contracts",
                    [],
                )
                or []
            )

            audit.record(
                stage="OPTION_CHAIN",
                status="COMPLETED",
                decision="CHAIN_BUILT",
                details={
                    "contract_count": (
                        len(
                            contracts
                        )
                    ),
                },
            )

        # ---------------------------------
        # CONTRACT SELECTION AUDIT
        # ---------------------------------

        contract = result.get(
            "contract"
        )

        if (
            option_chain is not None
            and contract is not None
        ):

            selected = bool(
                contract.get(
                    "selected",
                    False,
                )
            )

            audit.record(
                stage="CONTRACT_SELECTION",
                status=(
                    "PASSED"
                    if selected
                    else "BLOCKED"
                ),
                decision=(
                    "CONTRACT_SELECTED"
                    if selected
                    else "NO_CONTRACT"
                ),
                reasons=(
                    contract.get(
                        "reasons",
                        [],
                    )
                ),
                details={
                    "symbol": (
                        contract.get(
                            "symbol"
                        )
                    ),
                    "option_type": (
                        contract.get(
                            "option_type"
                        )
                    ),
                    "strike": (
                        contract.get(
                            "strike"
                        )
                    ),
                },
            )

        # ---------------------------------
        # TRADE PLAN AUDIT
        # ---------------------------------

        trade_plan = result.get(
            "trade_plan"
        )

        if trade_plan is not None:

            trade_allowed = bool(
                trade_plan.get(
                    "allowed",
                    False,
                )
            )

            audit.record(
                stage="TRADE_PLAN",
                status=(
                    "PASSED"
                    if trade_allowed
                    else "BLOCKED"
                ),
                decision=(
                    trade_plan.get(
                        "decision"
                    )
                ),
                reasons=(
                    trade_plan.get(
                        "reasons",
                        [],
                    )
                ),
                details={
                    "allowed": trade_allowed,
                    "lot_size": (
                        trade_plan.get(
                            "lot_size"
                        )
                    ),
                    "lots": (
                        trade_plan.get(
                            "lots"
                        )
                    ),
                    "quantity": (
                        trade_plan.get(
                            "quantity"
                        )
                    ),
                },
            )

        # ---------------------------------
        # FINAL DECISION AUDIT
        # ---------------------------------

        final_decision = result.get(
            "decision",
            "NO_TRADE",
        )

        audit.record(
            stage="FINAL_DECISION",
            status=(
                "PASSED"
                if final_decision
                in {
                    "TRADE_ALLOWED",
                    "TRADE_READY",
                }
                else "COMPLETED"
            ),
            decision=final_decision,
            reasons=(
                result.get(
                    "reasons",
                    [],
                )
            ),
        )

        result[
            "audit_trail"
        ] = audit.build_summary(
            final_decision=(
                final_decision
            )
        )

        # ---------------------------------
        # OPTIONAL PERSISTENT AUDIT LOGGING
        # ---------------------------------
        #
        # Persistence is isolated from trading
        # authorization. A logging failure must
        # never change the core pipeline decision.

        audit_persistence = {
            "enabled": (
                self.persist_audit
            ),
            "persisted": False,
            "error": None,
        }

        if self.persist_audit:

            try:

                logger = (
                    self.audit_logger
                    if self.audit_logger is not None
                    else DecisionAuditLogger()
                )

                logger.log(
                    audit_trail=(
                        result[
                            "audit_trail"
                        ]
                    ),
                    metadata={
                        "exchange": exchange,
                        "symboltoken": (
                            str(
                                symboltoken
                            )
                        ),
                        "underlying": (
                            str(
                                underlying
                            )
                            .strip()
                            .upper()
                        ),
                        "spot_price": (
                            spot_price
                        ),
                        "final_decision": (
                            final_decision
                        ),
                    },
                )

                audit_persistence[
                    "persisted"
                ] = True

            except Exception as exc:

                audit_persistence[
                    "error"
                ] = str(
                    exc
                )

        result[
            "audit_persistence"
        ] = audit_persistence

        return result

    def _analyse_core(
        self,
        exchange,
        symboltoken,
        underlying,
        spot_price,
        strikes_each_side=5,
        end_time=None,
        capital=None,
        risk_percent=1.0,
        minimum_risk_reward=2.0,
        maximum_capital_usage_percent=100.0,
        option_stop_percent=20.0,
        atr_stop_multiplier=1.0,
        breakout_buffer_percent=0.0,
        confirmation_interval="FIVE_MINUTE",
        enforce_market_session=False,
        session_now=None,
        maximum_candle_age_minutes=10,
    ):
        """
        Run the core safety-gated option decision pipeline.

        Possible decisions:
        - MARKET_CLOSED
        - MARKET_HOLIDAY
        - STALE_MARKET_DATA
        - NO_TRADE
        - WAITING_FOR_BREAKOUT
        - WAITING_FOR_BREAKDOWN
        - TRADE_READY
        - TRADE_ALLOWED
        - TRADE_REJECTED
        """

        # ---------------------------------
        # BASIC INPUT VALIDATION
        # ---------------------------------

        if spot_price is None:
            raise ValueError(
                "Spot price must be greater than zero."
            )

        try:

            if float(
                spot_price
            ) <= 0:

                raise ValueError(
                    "Spot price must be greater than zero."
                )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "Spot price must be greater than zero."
            ) from exc

        if (
            capital is not None
            and capital <= 0
        ):
            raise ValueError(
                "Capital must be greater than zero."
            )

        if maximum_candle_age_minutes <= 0:
            raise ValueError(
                "maximum_candle_age_minutes must "
                "be greater than zero."
            )

        # ---------------------------------
        # LIVE SPOT-PRICE INTEGRITY GATE
        # ---------------------------------

        spot_price = validate_live_price(
            spot_price
        )

        # ---------------------------------
        # INITIAL MARKET SESSION SAFETY GATE
        # ---------------------------------

        session_status = None

        if enforce_market_session:

            session_status = (
                evaluate_market_session(
                    now=session_now,
                    maximum_candle_age_minutes=(
                        maximum_candle_age_minutes
                    ),
                    holiday_calendar=(
                        self.holiday_calendar
                    ),
                )
            )

            if not session_status.get(
                "market_open",
                False,
            ):

                session_decision = (
                    session_status.get(
                        "status",
                        "MARKET_CLOSED",
                    )
                )

                return {
                    "decision": session_decision,
                    "market_decision": "NO_TRADE",
                    "direction": "NEUTRAL",
                    "market_analysis": None,
                    "session_status": session_status,
                    "market_session": session_status,
                    "setup_trigger": None,
                    "completed_candle": None,
                    "breakout_confirmation": None,
                    "option_chain": None,
                    "contract": self._no_contract(
                        "Market session safety gate "
                        "did not authorize live analysis."
                    ),
                    "trade_plan": None,
                    "reasons": session_status.get(
                        "reasons",
                        [],
                    ),
                }

        # ---------------------------------
        # MARKET ANALYSIS
        # ---------------------------------

        market_result = (
            self.analysis_pipeline.analyse(
                exchange=exchange,
                symboltoken=symboltoken,
                end_time=end_time,
            )
        )

        strategy = market_result.get(
            "strategy",
            {},
        ) or {}

        market_decision = str(
            strategy.get(
                "decision",
                "NO_TRADE",
            )
        ).upper()

        direction = str(
            strategy.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        candlestick = market_result.get(
            "candlestick",
            {},
        ) or {}

        chart = self._extract_chart_analysis(
            market_result
        )

        setup_trigger = None
        breakout_confirmation = None
        completed_candle = None

        trade_authorized = (
            market_decision == "TRADE"
        )

        # ---------------------------------
        # NO DIRECT TRADE AUTHORIZATION
        # CHECK FOR SETUP + CANDLE CONFIRMATION
        # ---------------------------------

        if not trade_authorized:

            setup_trigger = (
                evaluate_setup_trigger(
                    strategy=strategy,
                    chart=chart,
                    candlestick=candlestick,
                    current_price=spot_price,
                    breakout_buffer_percent=(
                        breakout_buffer_percent
                    ),
                )
            )

            setup_status = str(
                setup_trigger.get(
                    "status",
                    "NO_SETUP",
                )
            ).upper()

            confirmation_candidate = (
                setup_status
                in {
                    "WAITING_FOR_BREAKOUT",
                    "WAITING_FOR_BREAKDOWN",
                    "TRIGGERED",
                }
                and setup_trigger.get(
                    "trigger_price"
                )
                is not None
                and direction
                in {
                    "BULLISH",
                    "BEARISH",
                }
            )

            if not confirmation_candidate:

                return {
                    "decision": "NO_TRADE",
                    "market_decision": market_decision,
                    "direction": direction,
                    "market_analysis": market_result,
                    "session_status": session_status,
                    "market_session": session_status,
                    "setup_trigger": setup_trigger,
                    "completed_candle": None,
                    "breakout_confirmation": None,
                    "option_chain": None,
                    "contract": self._no_contract(
                        "Market analysis did not "
                        "authorize a trade."
                    ),
                    "trade_plan": None,
                }

            # ---------------------------------
            # FETCH LATEST COMPLETED CANDLE
            # ---------------------------------

            completed_candle = (
                self.completed_candle_service
                .get_latest_completed_candle(
                    exchange=exchange,
                    symboltoken=symboltoken,
                    interval=(
                        confirmation_interval
                    ),
                )
            )

            # ---------------------------------
            # COMPLETED CANDLE INTEGRITY GATE
            # ---------------------------------

            completed_candle = validate_candle(
                completed_candle
            )

            # ---------------------------------
            # COMPLETED CANDLE FRESHNESS GATE
            # ---------------------------------

            if enforce_market_session:

                session_status = (
                    evaluate_market_session(
                        now=session_now,
                        candle_timestamp=(
                            completed_candle.get(
                                "timestamp"
                            )
                        ),
                        maximum_candle_age_minutes=(
                            maximum_candle_age_minutes
                        ),
                        holiday_calendar=(
                            self.holiday_calendar
                        ),
                    )
                )

                if not session_status.get(
                    "allowed",
                    False,
                ):

                    session_decision = (
                        session_status.get(
                            "status",
                            "STALE_MARKET_DATA",
                        )
                    )

                    return {
                        "decision": session_decision,
                        "market_decision": market_decision,
                        "direction": direction,
                        "market_analysis": market_result,
                        "session_status": session_status,
                        "market_session": session_status,
                        "setup_trigger": setup_trigger,
                        "completed_candle": completed_candle,
                        "breakout_confirmation": None,
                        "option_chain": None,
                        "contract": self._no_contract(
                            "Market session, holiday, "
                            "or candle-freshness safety "
                            "gate failed."
                        ),
                        "trade_plan": None,
                        "reasons": session_status.get(
                            "reasons",
                            [],
                        ),
                    }

            # ---------------------------------
            # CONFIRM BREAKOUT / BREAKDOWN
            # ---------------------------------

            breakout_confirmation = (
                confirm_breakout(
                    direction=direction,
                    trigger_price=(
                        setup_trigger[
                            "trigger_price"
                        ]
                    ),
                    candle_close=(
                        completed_candle[
                            "close"
                        ]
                    ),
                    candle_high=(
                        completed_candle.get(
                            "high"
                        )
                    ),
                    candle_low=(
                        completed_candle.get(
                            "low"
                        )
                    ),
                    current_volume=(
                        completed_candle.get(
                            "volume"
                        )
                    ),
                    confirmation_buffer_percent=0.0,
                    require_volume=False,
                    require_momentum=False,
                )
            )

            # ---------------------------------
            # CANDLE DID NOT CONFIRM
            # ---------------------------------

            if not breakout_confirmation.get(
                "confirmed",
                False,
            ):

                waiting_decision = (
                    "WAITING_FOR_BREAKOUT"
                    if direction == "BULLISH"
                    else "WAITING_FOR_BREAKDOWN"
                )

                return {
                    "decision": waiting_decision,
                    "market_decision": market_decision,
                    "direction": direction,
                    "market_analysis": market_result,
                    "session_status": session_status,
                    "market_session": session_status,
                    "setup_trigger": setup_trigger,
                    "completed_candle": completed_candle,
                    "breakout_confirmation": (
                        breakout_confirmation
                    ),
                    "option_chain": None,
                    "contract": self._no_contract(
                        "Completed candle has not "
                        "confirmed the market trigger."
                    ),
                    "trade_plan": None,
                }

            trade_authorized = True

        # ---------------------------------
        # VALIDATE AUTHORIZED DIRECTION
        # ---------------------------------

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return {
                "decision": "NO_TRADE",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "session_status": session_status,
                "market_session": session_status,
                "setup_trigger": setup_trigger,
                "completed_candle": completed_candle,
                "breakout_confirmation": (
                    breakout_confirmation
                ),
                "option_chain": None,
                "contract": self._no_contract(
                    "Trade was authorized without "
                    "a valid direction."
                ),
                "trade_plan": None,
            }

        # ---------------------------------
        # BUILD LIVE OPTION CHAIN
        # ---------------------------------

        option_chain = (
            self.option_chain_builder.build_chain(
                underlying=underlying,
                spot_price=spot_price,
                strikes_each_side=(
                    strikes_each_side
                ),
            )
        )

        contracts = option_chain.get(
            "contracts",
            [],
        )

        # ---------------------------------
        # SELECT BEST CONTRACT
        # ---------------------------------

        contract = select_option_contract(
            contracts=contracts,
            direction=direction,
            spot_price=spot_price,
            require_delta=False,
        )

        if not contract.get(
            "selected",
            False,
        ):
            return {
                "decision": "NO_TRADE",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "session_status": session_status,
                "market_session": session_status,
                "setup_trigger": setup_trigger,
                "completed_candle": completed_candle,
                "breakout_confirmation": (
                    breakout_confirmation
                ),
                "option_chain": option_chain,
                "contract": contract,
                "trade_plan": None,
            }

        # ---------------------------------
        # STOP AFTER CONTRACT SELECTION
        # WHEN CAPITAL IS NOT PROVIDED
        # ---------------------------------

        if capital is None:
            return {
                "decision": "TRADE_READY",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "session_status": session_status,
                "market_session": session_status,
                "setup_trigger": setup_trigger,
                "completed_candle": completed_candle,
                "breakout_confirmation": (
                    breakout_confirmation
                ),
                "option_chain": option_chain,
                "contract": contract,
                "trade_plan": None,
            }

        # ---------------------------------
        # EXTRACT MARKET RISK INPUTS
        # ---------------------------------

        market_inputs = (
            self._extract_market_inputs(
                market_result
            )
        )

        atr = market_inputs[
            "atr"
        ]

        support = market_inputs[
            "support"
        ]

        resistance = market_inputs[
            "resistance"
        ]

        if atr <= 0:
            return {
                "decision": "TRADE_REJECTED",
                "market_decision": market_decision,
                "direction": direction,
                "market_analysis": market_result,
                "session_status": session_status,
                "market_session": session_status,
                "setup_trigger": setup_trigger,
                "completed_candle": completed_candle,
                "breakout_confirmation": (
                    breakout_confirmation
                ),
                "option_chain": option_chain,
                "contract": contract,
                "trade_plan": None,
                "reasons": [
                    "Valid ATR data is required "
                    "to build the trade plan."
                ],
            }

        # ---------------------------------
        # BUILD COMPLETE TRADE PLAN
        # ---------------------------------

        trade_plan = build_trade_plan(
            contract=contract,
            direction=direction,
            spot_price=spot_price,
            atr=atr,
            capital=capital,
            support=support,
            resistance=resistance,
            risk_percent=risk_percent,
            minimum_risk_reward=(
                minimum_risk_reward
            ),
            maximum_capital_usage_percent=(
                maximum_capital_usage_percent
            ),
            option_stop_percent=(
                option_stop_percent
            ),
            atr_stop_multiplier=(
                atr_stop_multiplier
            ),
        )

        # ---------------------------------
        # FINAL AUTHORIZATION
        # ---------------------------------

        if trade_plan.get(
            "allowed",
            False,
        ):
            final_decision = (
                "TRADE_ALLOWED"
            )

        else:
            final_decision = (
                "TRADE_REJECTED"
            )

        return {
            "decision": final_decision,
            "market_decision": market_decision,
            "direction": direction,
            "market_analysis": market_result,
            "session_status": session_status,
            "market_session": session_status,
            "setup_trigger": setup_trigger,
            "completed_candle": completed_candle,
            "breakout_confirmation": (
                breakout_confirmation
            ),
            "option_chain": option_chain,
            "contract": contract,
            "trade_plan": trade_plan,
        }