"""
Live read-only NIFTY option trade-plan test with paper trading.

Flow:
1. Check whether the Indian market session is open.
2. Check whether today is a configured NSE trading holiday.
3. Stop safely before calling Angel One if the market is closed.
4. Fetch and validate the current NIFTY spot price.
5. Run the complete live option decision pipeline.
6. Persist the decision audit trail.
7. Send the completed decision to the paper-trading orchestrator.
8. Open a paper trade only when the pipeline authorizes TRADE_ALLOWED.
9. Persist paper-trade state and recover it after restart.

IMPORTANT:
- Paper trading only.
- No real broker order is placed.
- Paper-trading failures cannot change the pipeline decision.
"""

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.decision_audit_logger import (
    DecisionAuditLogger,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)

from services.market_session_guard import (
    evaluate_market_session,
)

from services.market_data_validator import (
    MarketDataValidationError,
    validate_live_price,
)

from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)

from services.paper_trade_repository import (
    PaperTradeRepository,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)

from services.paper_trading_orchestrator import (
    PaperTradingOrchestrator,
)
from services.paper_trading_risk_guard import (
    PaperTradingRiskGuard,
)

# ============================================================
# CONFIGURATION
# ============================================================
PAPER_MAX_OPEN_POSITIONS = 1

PAPER_MAX_TRADES_PER_DAY = 5

PAPER_MAX_DAILY_REALIZED_LOSS = 500.0

PAPER_BLOCK_DUPLICATE_POSITIONS = True

PAPER_TRADING_KILL_SWITCH = False
NIFTY_TOKEN = "99926000"

CAPITAL = 10_000

RISK_PERCENT = 1.0

BREAKOUT_BUFFER_PERCENT = 0.0

CONFIRMATION_INTERVAL = "FIVE_MINUTE"

ENFORCE_MARKET_SESSION = True

MAXIMUM_CANDLE_AGE_MINUTES = 10

PERSIST_AUDIT = True

ENABLE_PAPER_TRADING = True

PERSIST_PAPER_TRADES = True

NSE_HOLIDAY_CALENDAR = (
    get_nse_holiday_calendar()
)


# ============================================================
# HEADER
# ============================================================

print("\n================================")
print("AI TRADING COPILOT")
print("LIVE NIFTY TRADE PLAN")
print("================================")

print(
    f"\nCapital: ₹{CAPITAL:,.2f}"
)

print(
    f"Risk per trade: {RISK_PERCENT}%"
)

print(
    "Market session enforcement:",
    ENFORCE_MARKET_SESSION,
)

print(
    "Maximum candle age:",
    MAXIMUM_CANDLE_AGE_MINUTES,
    "minutes",
)

print(
    "Paper trading:",
    ENABLE_PAPER_TRADING,
)

print(
    "Paper trade persistence:",
    PERSIST_PAPER_TRADES,
)


# ============================================================
# PRE-CHECK MARKET SESSION
# ============================================================

pre_session = None

if ENFORCE_MARKET_SESSION:

    print(
        "\nChecking Indian market session..."
    )

    pre_session = (
        evaluate_market_session(
            maximum_candle_age_minutes=(
                MAXIMUM_CANDLE_AGE_MINUTES
            ),
            holiday_calendar=(
                NSE_HOLIDAY_CALENDAR
            ),
        )
    )

    print("\nMARKET SESSION PRE-CHECK")
    print("========================")

    print(
        "Status:",
        pre_session.get(
            "status"
        ),
    )

    print(
        "Allowed:",
        pre_session.get(
            "allowed"
        ),
    )

    print(
        "Market Open:",
        pre_session.get(
            "market_open"
        ),
    )

    print(
        "Trading Weekday:",
        pre_session.get(
            "is_weekday"
        ),
    )

    print(
        "Market Holiday:",
        pre_session.get(
            "is_market_holiday"
        ),
    )

    print(
        "Within Market Hours:",
        pre_session.get(
            "within_market_hours"
        ),
    )

    print(
        "Current Time:",
        pre_session.get(
            "current_time"
        ),
    )

    reasons = (
        pre_session.get(
            "reasons",
            [],
        )
    )

    if reasons:

        print("\nSESSION REASONS")

        for reason in reasons:

            print(
                "-",
                reason,
            )

    # --------------------------------------------------------
    # STOP BEFORE ANY BROKER API CALL WHEN MARKET IS CLOSED
    # --------------------------------------------------------

    if not pre_session.get(
        "market_open",
        False,
    ):

        print("\n================================")
        print("FINAL STATUS")
        print("================================")

        print(
            "Decision:",
            pre_session.get(
                "status",
                "MARKET_CLOSED",
            ),
        )

        if (
            pre_session.get(
                "status"
            )
            == "MARKET_HOLIDAY"
        ):

            print(
                "The NSE holiday safety gate "
                "blocked live analysis before any "
                "Angel One market-data request."
            )

        else:

            print(
                "The market-session safety gate "
                "blocked live analysis before any "
                "Angel One market-data request."
            )

        print(
            "No live spot data was requested."
        )

        print(
            "No option chain was requested."
        )

        print(
            "No option contract was selected."
        )

        print(
            "No trade was authorized."
        )

        print(
            "No paper trade was opened."
        )

        print(
            "\nREAD-ONLY ANALYSIS COMPLETE"
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        raise SystemExit(
            0
        )


# ============================================================
# SETUP PAPER TRADING
# ============================================================

paper_trade_repository = (
    PaperTradeRepository()
)

paper_trading_engine = (
    PaperTradingEngine(
        repository=(
            paper_trade_repository
        ),
        persist_state=(
            PERSIST_PAPER_TRADES
        ),
    )
)

paper_trading_risk_guard = (
    PaperTradingRiskGuard(
        max_open_positions=(
            PAPER_MAX_OPEN_POSITIONS
        ),
        max_trades_per_day=(
            PAPER_MAX_TRADES_PER_DAY
        ),
        max_daily_realized_loss=(
            PAPER_MAX_DAILY_REALIZED_LOSS
        ),
        block_duplicate_positions=(
            PAPER_BLOCK_DUPLICATE_POSITIONS
        ),
        kill_switch=(
            PAPER_TRADING_KILL_SWITCH
        ),
    )
)

paper_trading_orchestrator = (
    PaperTradingOrchestrator(
        paper_trading_engine=(
            paper_trading_engine
        ),
        enabled=(
            ENABLE_PAPER_TRADING
        ),
        risk_guard=(
            paper_trading_risk_guard
        ),
    )
)

recovered_paper_trades = []

try:

    recovered_paper_trades = (
        paper_trading_engine.recover_trades()
    )

    print("\nPAPER TRADING STARTUP")
    print("=====================")

    print(
        "Enabled:",
        ENABLE_PAPER_TRADING,
    )

    print(
        "Persistence:",
        PERSIST_PAPER_TRADES,
    )

    print(
        "Recovered Trades:",
        len(
            recovered_paper_trades
        ),
    )

    print(
        "Open Trades:",
        paper_trading_engine.count_open_trades(),
    )

    print(
        "Closed Trades:",
        paper_trading_engine.count_closed_trades(),
    )

except Exception as exc:

    # Paper-trading recovery failure must not
    # affect live market analysis.

    recovered_paper_trades = []

    print("\nPAPER TRADING RECOVERY WARNING")
    print("==============================")

    print(
        "Paper-trade recovery failed."
    )

    print(
        "Live market analysis will continue."
    )

    print(
        "Error:",
        str(
            exc
        ),
    )


# ============================================================
# FETCH CURRENT NIFTY SPOT
# ============================================================

print(
    "\nFetching live NIFTY spot..."
)

client = (
    AngelMarketDataClient()
)

try:

    response = (
        client.get_market_data(
            mode="LTP",
            exchange_tokens={
                "NSE": [
                    NIFTY_TOKEN
                ]
            },
        )
    )

except Exception as exc:

    print("\n================================")
    print("LIVE DATA ERROR")
    print("================================")

    print(
        "Unable to fetch live NIFTY spot data."
    )

    print(
        "The broker API may be temporarily "
        "unavailable or the network request "
        "may have timed out."
    )

    print(
        "Error:",
        str(
            exc
        ),
    )

    print(
        "\nNo trade analysis was authorized."
    )

    print(
        "No paper trade was opened."
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    raise SystemExit(
        1
    )


# ============================================================
# EXTRACT FETCHED MARKET DATA
# ============================================================

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

if not fetched:

    print("\n================================")
    print("LIVE DATA ERROR")
    print("================================")

    print(
        "No NIFTY spot data was received."
    )

    print(
        "No trade analysis was authorized."
    )

    print(
        "No option chain was requested."
    )

    print(
        "No option contract was selected."
    )

    print(
        "No paper trade was opened."
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    raise SystemExit(
        1
    )


# ============================================================
# VALIDATE LIVE NIFTY SPOT
# ============================================================

raw_spot_price = (
    fetched[0].get(
        "ltp"
    )
)

try:

    spot_price = (
        validate_live_price(
            raw_spot_price
        )
    )

except MarketDataValidationError as exc:

    print("\n================================")
    print("LIVE DATA INTEGRITY ERROR")
    print("================================")

    print(
        "The received NIFTY spot price "
        "failed mandatory integrity validation."
    )

    print(
        "Raw Spot Value:",
        raw_spot_price,
    )

    print(
        "Validation Error:",
        str(
            exc
        ),
    )

    print(
        "\nThe invalid market data was rejected "
        "before entering the trading pipeline."
    )

    print(
        "No trade analysis was authorized."
    )

    print(
        "No option chain was requested."
    )

    print(
        "No option contract was selected."
    )

    print(
        "No paper trade was opened."
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    raise SystemExit(
        1
    )


print(
    f"NIFTY Spot: {spot_price}"
)

print(
    "Live spot integrity validation: PASSED"
)


# ============================================================
# SETUP DECISION AUDIT LOGGING
# ============================================================

audit_logger = (
    DecisionAuditLogger()
)


# ============================================================
# SETUP LIVE DECISION PIPELINE
# ============================================================

pipeline = (
    LiveOptionDecisionPipeline(
        market_client=client,
        audit_logger=(
            audit_logger
        ),
        persist_audit=(
            PERSIST_AUDIT
        ),
    )
)


# ============================================================
# RUN COMPLETE LIVE PIPELINE
# ============================================================

print(
    "\nRunning complete "
    "risk-controlled pipeline..."
)

try:

    result = (
        pipeline.analyse(
            exchange="NSE",
            symboltoken=(
                NIFTY_TOKEN
            ),
            underlying="NIFTY",
            spot_price=(
                spot_price
            ),
            strikes_each_side=5,
            capital=(
                CAPITAL
            ),
            risk_percent=(
                RISK_PERCENT
            ),
            breakout_buffer_percent=(
                BREAKOUT_BUFFER_PERCENT
            ),
            confirmation_interval=(
                CONFIRMATION_INTERVAL
            ),
            enforce_market_session=(
                ENFORCE_MARKET_SESSION
            ),
            maximum_candle_age_minutes=(
                MAXIMUM_CANDLE_AGE_MINUTES
            ),
        )
    )

except MarketDataValidationError as exc:

    print("\n================================")
    print("MARKET DATA INTEGRITY ERROR")
    print("================================")

    print(
        "The trading pipeline rejected "
        "invalid market data."
    )

    print(
        "Validation Error:",
        str(
            exc
        ),
    )

    print(
        "\nNo trade was authorized."
    )

    print(
        "No paper trade was opened."
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    raise SystemExit(
        1
    )

except Exception as exc:

    print("\n================================")
    print("PIPELINE ERROR")
    print("================================")

    print(
        "The live analysis pipeline "
        "could not complete safely."
    )

    print(
        "Error:",
        str(
            exc
        ),
    )

    print(
        "\nNo trade was authorized."
    )

    print(
        "No paper trade was opened."
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    raise SystemExit(
        1
    )


# ============================================================
# PAPER TRADING ORCHESTRATION
# ============================================================

paper_trading_result = None

try:

    # --------------------------------------------------------
    # BUILD SOURCE DECISION REFERENCE
    # --------------------------------------------------------

    audit_trail = (
        result.get(
            "audit_trail",
            {},
        )
        or {}
    )

    audit_events = (
        audit_trail.get(
            "events",
            [],
        )
        or []
    )

    source_event = (
        audit_events[-1]
        if audit_events
        else {}
    )

    source_timestamp = (
        source_event.get(
            "timestamp"
        )
        or "NO_AUDIT_TIMESTAMP"
    )

    source_sequence = (
        source_event.get(
            "sequence"
        )
    )

    if source_sequence is None:

        source_sequence = (
            len(
                audit_events
            )
        )

    final_pipeline_decision = (
        result.get(
            "decision",
            "UNKNOWN"
        )
    )

    source_decision_id = (
        f"NSE:"
        f"NIFTY:"
        f"{NIFTY_TOKEN}:"
        f"{source_timestamp}:"
        f"{source_sequence}:"
        f"{final_pipeline_decision}"
    )

    source_audit_ref = (
        source_decision_id
    )

    # --------------------------------------------------------
    # PROCESS DECISION
    # --------------------------------------------------------

    paper_trading_result = (
        paper_trading_orchestrator.process_decision(
            pipeline_result=(
                result
            ),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken=(
                NIFTY_TOKEN
            ),
            source_decision_id=(
                source_decision_id
            ),
            source_audit_ref=(
                source_audit_ref
            ),
            metadata={
                "entry_point": (
                    "live_option_decision_nifty.py"
                ),
                "spot_price": (
                    spot_price
                ),
                "paper_trading_enabled": (
                    ENABLE_PAPER_TRADING
                ),
                "paper_trade_persistence": (
                    PERSIST_PAPER_TRADES
                ),
                "audit_persistence": (
                    PERSIST_AUDIT
                ),
            },
        )
    )

except Exception as exc:

    # --------------------------------------------------------
    # CRITICAL SAFETY BOUNDARY
    # --------------------------------------------------------
    #
    # Paper-trading failure must never:
    #
    # - change the pipeline decision
    # - authorize a real order
    # - modify market analysis
    # - crash successful market analysis
    #

    paper_trading_result = {
        "status": "ERROR",
        "opened": False,
        "trade_id": None,
        "reason": (
            "PAPER_TRADING_ORCHESTRATION_FAILED"
        ),
        "error": str(
            exc
        ),
    }


# ============================================================
# MARKET SESSION STATUS
# ============================================================

market_session = (
    result.get(
        "session_status"
    )
    or result.get(
        "market_session"
    )
    or result.get(
        "session_guard"
    )
)

if market_session:

    print("\nMARKET SESSION")
    print("==============")

    print(
        "Status:",
        market_session.get(
            "status"
        ),
    )

    print(
        "Allowed:",
        market_session.get(
            "allowed"
        ),
    )

    print(
        "Market Open:",
        market_session.get(
            "market_open"
        ),
    )

    print(
        "Trading Weekday:",
        market_session.get(
            "is_weekday"
        ),
    )

    print(
        "Market Holiday:",
        market_session.get(
            "is_market_holiday"
        ),
    )

    print(
        "Within Market Hours:",
        market_session.get(
            "within_market_hours"
        ),
    )

    print(
        "Current Time:",
        market_session.get(
            "current_time"
        ),
    )

    print(
        "Candle Timestamp:",
        market_session.get(
            "candle_timestamp"
        ),
    )

    print(
        "Candle Age:",
        market_session.get(
            "candle_age_minutes"
        ),
        "minutes",
    )

    print(
        "Candle Fresh:",
        market_session.get(
            "candle_fresh"
        ),
    )

    reasons = (
        market_session.get(
            "reasons",
            [],
        )
    )

    if reasons:

        print("\nSESSION REASONS")

        for reason in reasons:

            print(
                "-",
                reason,
            )


# ============================================================
# MARKET DECISION
# ============================================================

print("\nMARKET DECISION")
print("================")

print(
    "Market Decision:",
    result.get(
        "market_decision"
    ),
)

print(
    "Direction:",
    result.get(
        "direction"
    ),
)

market_analysis = (
    result.get(
        "market_analysis",
        {},
    )
    or {}
)

strategy = (
    market_analysis.get(
        "strategy",
        {},
    )
    or {}
)

print(
    "Strategy:",
    strategy.get(
        "strategy"
    ),
)

print(
    "Confidence:",
    strategy.get(
        "confidence"
    ),
)

print(
    "Risk Flags:",
    strategy.get(
        "risk_flags",
        [],
    ),
)


# ============================================================
# SETUP / TRIGGER STATUS
# ============================================================

setup_trigger = (
    result.get(
        "setup_trigger"
    )
)

if setup_trigger:

    print("\nSETUP STATUS")
    print("============")

    print(
        "Status:",
        setup_trigger.get(
            "status"
        ),
    )

    print(
        "Direction:",
        setup_trigger.get(
            "direction"
        ),
    )

    print(
        "Trigger Type:",
        setup_trigger.get(
            "trigger_type"
        ),
    )

    trigger_price = (
        setup_trigger.get(
            "trigger_price"
        )
    )

    current_price = (
        setup_trigger.get(
            "current_price"
        )
    )

    if (
        trigger_price is not None
        and current_price is not None
    ):

        print(
            "Trigger Price:",
            trigger_price,
        )

        distance = abs(
            float(
                trigger_price
            )
            - float(
                current_price
            )
        )

        print(
            "Distance to Trigger:",
            round(
                distance,
                2,
            ),
            "points",
        )

    print(
        "Support:",
        setup_trigger.get(
            "support"
        ),
    )

    print(
        "Resistance:",
        setup_trigger.get(
            "resistance"
        ),
    )

    reasons = (
        setup_trigger.get(
            "reasons",
            [],
        )
    )

    if reasons:

        print("\nSETUP REASONS")

        for reason in reasons:

            print(
                "-",
                reason,
            )


# ============================================================
# COMPLETED CANDLE
# ============================================================

completed_candle = (
    result.get(
        "completed_candle"
    )
)

if completed_candle:

    print("\nCOMPLETED CANDLE")
    print("================")

    print(
        "Timestamp:",
        completed_candle.get(
            "timestamp"
        ),
    )

    print(
        "Open:",
        completed_candle.get(
            "open"
        ),
    )

    print(
        "High:",
        completed_candle.get(
            "high"
        ),
    )

    print(
        "Low:",
        completed_candle.get(
            "low"
        ),
    )

    print(
        "Close:",
        completed_candle.get(
            "close"
        ),
    )

    print(
        "Volume:",
        completed_candle.get(
            "volume"
        ),
    )


# ============================================================
# BREAKOUT / BREAKDOWN CONFIRMATION
# ============================================================

breakout_confirmation = (
    result.get(
        "breakout_confirmation"
    )
)

if breakout_confirmation:

    print("\nTRIGGER CONFIRMATION")
    print("====================")

    print(
        "Status:",
        breakout_confirmation.get(
            "status"
        ),
    )

    print(
        "Confirmed:",
        breakout_confirmation.get(
            "confirmed"
        ),
    )

    print(
        "Direction:",
        breakout_confirmation.get(
            "direction"
        ),
    )

    print(
        "Trigger Type:",
        breakout_confirmation.get(
            "trigger_type"
        ),
    )

    print(
        "Trigger Price:",
        breakout_confirmation.get(
            "trigger_price"
        ),
    )

    print(
        "Confirmation Price:",
        breakout_confirmation.get(
            "confirmation_price"
        ),
    )

    print(
        "Candle Close:",
        breakout_confirmation.get(
            "candle_close"
        ),
    )

    reasons = (
        breakout_confirmation.get(
            "reasons",
            [],
        )
    )

    if reasons:

        print("\nCONFIRMATION REASONS")

        for reason in reasons:

            print(
                "-",
                reason,
            )

    failed_conditions = (
        breakout_confirmation.get(
            "failed_conditions",
            [],
        )
    )

    if failed_conditions:

        print("\nFAILED CONDITIONS")

        for reason in failed_conditions:

            print(
                "-",
                reason,
            )


# ============================================================
# CONTRACT SELECTION
# ============================================================

contract = (
    result.get(
        "contract",
        {},
    )
    or {}
)

print("\nOPTION CONTRACT")
print("===============")

if contract.get(
    "selected",
    False,
):

    print(
        "Symbol:",
        contract.get(
            "symbol"
        ),
    )

    print(
        "Option Type:",
        contract.get(
            "option_type"
        ),
    )

    print(
        "Strike:",
        contract.get(
            "strike"
        ),
    )

    print(
        "Expiry:",
        contract.get(
            "expiry"
        ),
    )

    print(
        "Premium:",
        contract.get(
            "premium"
        ),
    )

    print(
        "Actual Lot Size:",
        contract.get(
            "lot_size"
        ),
    )

    print(
        "Selection Score:",
        contract.get(
            "score"
        ),
    )

else:

    print(
        "No contract selected."
    )

    for reason in contract.get(
        "reasons",
        [],
    ):

        print(
            "-",
            reason,
        )


# ============================================================
# TRADE PLAN
# ============================================================

trade_plan = (
    result.get(
        "trade_plan"
    )
)

if trade_plan:

    print("\nTRADE PLAN")
    print("==========")

    print(
        "Plan Decision:",
        trade_plan.get(
            "decision"
        ),
    )

    print(
        "Entry Price:",
        trade_plan.get(
            "entry_price"
        ),
    )

    print(
        "Stop Loss:",
        trade_plan.get(
            "stop_loss_price"
        ),
    )

    print(
        "Target:",
        trade_plan.get(
            "target_price"
        ),
    )

    print(
        "Risk/Reward:",
        trade_plan.get(
            "risk_reward_ratio"
        ),
    )

    print(
        "Lot Size:",
        trade_plan.get(
            "lot_size"
        ),
    )

    print(
        "Lot Size Source:",
        trade_plan.get(
            "lot_size_source"
        ),
    )

    print(
        "Lots:",
        trade_plan.get(
            "lots"
        ),
    )

    print(
        "Quantity:",
        trade_plan.get(
            "quantity"
        ),
    )

    print(
        "Required Capital: ₹"
        f"{trade_plan.get('required_capital', 0):,.2f}"
    )

    print(
        "Estimated Maximum Loss: ₹"
        f"{trade_plan.get('estimated_maximum_loss', 0):,.2f}"
    )

    reasons = (
        trade_plan.get(
            "reasons",
            [],
        )
    )

    if reasons:

        print("\nPLAN REASONS")

        for reason in reasons:

            print(
                "-",
                reason,
            )


# ============================================================
# FINAL STATUS
# ============================================================

print("\n================================")
print("FINAL STATUS")
print("================================")

final_decision = (
    result.get(
        "decision"
    )
)

print(
    "Decision:",
    final_decision,
)


if final_decision == "TRADE_ALLOWED":

    print(
        "The complete market, session, "
        "data-integrity, contract, and risk "
        "gates approved the trade plan."
    )


elif final_decision == "WAITING_FOR_BREAKOUT":

    print(
        "A bullish setup exists, but the "
        "breakout trigger has not been confirmed."
    )

    print(
        "No option contract was selected yet."
    )


elif final_decision == "WAITING_FOR_BREAKDOWN":

    print(
        "A bearish setup exists, but the "
        "breakdown trigger has not been confirmed."
    )

    print(
        "No option contract was selected yet."
    )


elif final_decision == "MARKET_HOLIDAY":

    print(
        "The NSE holiday safety gate blocked "
        "live trade authorization."
    )

    print(
        "No option contract or trade was authorized."
    )


elif final_decision == "MARKET_CLOSED":

    print(
        "The market-session safety gate blocked "
        "live trade authorization."
    )

    print(
        "No option contract or trade was authorized."
    )


elif final_decision == "STALE_MARKET_DATA":

    print(
        "The latest completed candle is too stale "
        "for safe live trade authorization."
    )

    print(
        "No option contract or trade was authorized."
    )


elif final_decision == "TRADE_REJECTED":

    print(
        "A trade setup reached the risk-planning "
        "stage but failed final authorization."
    )


elif final_decision == "NO_TRADE":

    print(
        "The current market analysis did not "
        "authorize a trade."
    )


else:

    print(
        "No actionable trade is currently authorized."
    )


# ============================================================
# PAPER TRADING STATUS
# ============================================================

print("\nPAPER TRADING")
print("=============")

print(
    "Enabled:",
    ENABLE_PAPER_TRADING,
)

print(
    "Persistence:",
    PERSIST_PAPER_TRADES,
)

if paper_trading_result:

    print(
        "Status:",
        paper_trading_result.get(
            "status"
        ),
    )

    print(
        "Opened:",
        paper_trading_result.get(
            "opened"
        ),
    )

    print(
        "Trade ID:",
        paper_trading_result.get(
            "trade_id"
        ),
    )

    print(
        "Reason:",
        paper_trading_result.get(
            "reason"
        ),
    )

    if paper_trading_result.get(
        "error"
    ):

        print(
            "Paper Trading Error:",
            paper_trading_result.get(
                "error"
            ),
        )

else:

    print(
        "No paper-trading result."
    )


# ============================================================
# SAFETY FOOTER
# ============================================================

print(
    "\nREAD-ONLY MARKET ANALYSIS COMPLETE"
)

print(
    "PAPER TRADING MAY BE ENABLED"
)

print(
    "NO REAL ORDER WAS PLACED"
)
