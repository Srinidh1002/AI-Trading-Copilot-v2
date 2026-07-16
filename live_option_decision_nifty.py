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

import argparse
import sys


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

from services.market_identity_guard import (
    validate_market_identity,
)

from services.market_session_configuration import (
    resolve_market_session_configuration,
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
from services.market_cycle_journal import (
    MarketCycleJournal,
)

from services.live_market_configuration import (
    resolve_live_market_configuration,
)


def configure_utf8_output():
    """Use UTF-8 for interactive and redirected runner output when supported."""

    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if reconfigure is not None:
            reconfigure(
                encoding="utf-8",
                errors="backslashreplace",
            )


configure_utf8_output()
# ============================================================
# LIVE MARKET RUNTIME SELECTION
# ============================================================


def parse_live_underlying(
    argv=None,
):
    parser = argparse.ArgumentParser(
        add_help=False,
    )

    parser.add_argument(
        "--underlying",
        default=None,
    )

    arguments, _ = (
        parser.parse_known_args(
            argv
        )
    )

    return arguments.underlying


def resolve_runtime_market_configuration(
    argv=None,
):
    requested_underlying = (
        parse_live_underlying(
            argv
        )
    )

    return resolve_live_market_configuration(
        requested_underlying
    )


# ============================================================
# CONFIGURATION
# ============================================================
PAPER_MAX_OPEN_POSITIONS = 1

PAPER_MAX_TRADES_PER_DAY = 5

PAPER_MAX_DAILY_REALIZED_LOSS = 500.0

PAPER_BLOCK_DUPLICATE_POSITIONS = True

PAPER_TRADING_KILL_SWITCH = False

UNDERLYING_CONFIGURATION = (
    resolve_runtime_market_configuration()
)

UNDERLYING = (
    UNDERLYING_CONFIGURATION.underlying
)

SPOT_EXCHANGE = (
    UNDERLYING_CONFIGURATION.exchange
)

SPOT_SYMBOLTOKEN = (
    UNDERLYING_CONFIGURATION.symboltoken
)

OPTION_EXCHANGE = (
    UNDERLYING_CONFIGURATION.option_exchange
)

CAPITAL = 10_000

RISK_PERCENT = 1.0

BREAKOUT_BUFFER_PERCENT = 0.0

CONFIRMATION_INTERVAL = "FIVE_MINUTE"

ENFORCE_MARKET_SESSION = True

MAXIMUM_CANDLE_AGE_MINUTES = 10

PERSIST_AUDIT = True

ENABLE_PAPER_TRADING = True

PERSIST_PAPER_TRADES = True

MARKET_SESSION_CONFIGURATION = (
    resolve_market_session_configuration(
        UNDERLYING
    )
)

MARKET_HOLIDAY_CALENDAR = (
    MARKET_SESSION_CONFIGURATION
    .holiday_calendar
)

MARKET_IDENTITY_VALIDATION = (
    validate_market_identity(
        UNDERLYING_CONFIGURATION,
        MARKET_SESSION_CONFIGURATION,
    )
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
                MARKET_HOLIDAY_CALENDAR
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

        # ----------------------------------------------------
        # RECORD SESSION-GATED RESEARCH CYCLE
        # ----------------------------------------------------

        session_gate_result = {
            "decision": (
                pre_session.get(
                    "status",
                    "MARKET_CLOSED",
                )
            ),
            "market_decision": None,
            "direction": None,
            "market_analysis": {},
            "setup_trigger": {},
            "contract": {},
            "session_status": (
                pre_session
            ),
        }

        session_gate_metadata = {
            "cycle_stage": (
                "SESSION_PRE_CHECK"
            ),
            "research_capture": True,
            "market_data_requested": False,
            "option_chain_requested": False,
            "contract_selected": False,
            "trade_authorized": False,
            "paper_trade_opened": False,
            "blocked_by_session_gate": True,
        }

        try:

            session_gate_journal = (
                MarketCycleJournal()
            )

            recorded_session_entry = (
                session_gate_journal.record_cycle(
                    pipeline_result=(
                        session_gate_result
                    ),
                    paper_trading_result=None,
                    metadata=(
                        session_gate_metadata
                    ),
                )
            )

            print(
                "\nMARKET CYCLE JOURNAL"
            )

            print(
                "===================="
            )

            print(
                "Recorded:",
                True,
            )

            print(
                "Decision:",
                recorded_session_entry.get(
                    "decision"
                ),
            )

            print(
                "Session Date:",
                recorded_session_entry.get(
                    "session_date"
                ),
            )

            print(
                "Cycle Stage:",
                recorded_session_entry.get(
                    "metadata",
                    {},
                ).get(
                    "cycle_stage"
                ),
            )

        except Exception as exc:

            print(
                "\nMARKET CYCLE JOURNAL WARNING"
            )

            print(
                "============================"
            )

            print(
                "The session-gated research "
                "cycle could not be persisted."
            )

            print(
                "Journal Error:",
                (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

            print(
                "The market-session safety gate "
                "remains enforced."
            )

            print(
                "No trade was authorized."
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
                SPOT_EXCHANGE: [
                    SPOT_SYMBOLTOKEN
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
            exchange=SPOT_EXCHANGE,
            symboltoken=(
                SPOT_SYMBOLTOKEN
            ),
            underlying=UNDERLYING,
            option_exchange=OPTION_EXCHANGE,
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
# MARKET CYCLE JOURNAL
# ============================================================

market_cycle_journal = (
    MarketCycleJournal()
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
        f"{SPOT_EXCHANGE}:"
        f"{UNDERLYING}:"
        f"{SPOT_SYMBOLTOKEN}:"
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
            underlying=UNDERLYING,
            exchange=SPOT_EXCHANGE,
            symboltoken=(
                SPOT_SYMBOLTOKEN
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
# MARKET CYCLE JOURNAL
# ============================================================
#
# Observability only.
#
# Journal persistence must never:
#
# - change the live pipeline decision
# - authorize a trade
# - reject a trade
# - modify paper-trading state
# - override live safety
# - crash successful market analysis
#
# ============================================================

market_cycle_journal_result = None

try:

    market_cycle_journal_result = (
        market_cycle_journal.record_cycle(
            pipeline_result=(
                result
            ),
            paper_trading_result=(
                paper_trading_result
            ),
            metadata={
                "entry_point": (
                    "live_option_decision_nifty.py"
                ),
                "underlying": (
                    UNDERLYING
                ),
                "exchange": (
                    SPOT_EXCHANGE
                ),
                "symboltoken": (
                    SPOT_SYMBOLTOKEN
                ),
                "spot_price": (
                    spot_price
                ),
                "capital": (
                    CAPITAL
                ),
                "risk_per_trade": (
                    RISK_PERCENT
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
    # CRITICAL OBSERVABILITY SAFETY BOUNDARY
    # --------------------------------------------------------
    #
    # Journal failure is fail-open for live analysis.
    #
    # The already completed market decision and paper-trading
    # result remain unchanged.
    #
    # --------------------------------------------------------

    market_cycle_journal_result = {
        "status": "ERROR",
        "persisted": False,
        "error": (
            f"{type(exc).__name__}: {exc}"
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
    "Direction Confidence:",
    strategy.get(
        "direction_confidence",
        strategy.get(
            "confidence"
        ),
    ),
)

print(
    "Evidence Strength:",
    strategy.get(
        "evidence_strength_score"
    ),
)

print(
    "Evidence Strength Label:",
    strategy.get(
        "evidence_strength_label"
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
# MARKET REGIME
# ============================================================

regime_analysis = (
    market_analysis.get(
        "regime",
        {},
    )
    or {}
)

if regime_analysis:

    print("\nMARKET REGIME")
    print("=============")

    print(
        "Primary Regime:",
        regime_analysis.get(
            "primary_regime"
        ),
    )

    print(
        "Trend:",
        regime_analysis.get(
            "trend"
        ),
    )

    print(
        "Volatility:",
        regime_analysis.get(
            "volatility"
        ),
    )

    print(
        "Confidence:",
        regime_analysis.get(
            "confidence"
        ),
    )

    regime_metrics = (
        regime_analysis.get(
            "metrics",
            {},
        )
        or {}
    )

    if regime_metrics:

        print(
            "ADX:",
            regime_metrics.get(
                "adx"
            ),
        )

        print(
            "ATR %:",
            regime_metrics.get(
                "atr_percent"
            ),
        )

        print(
            "Bollinger Band Width %:",
            regime_metrics.get(
                "bb_width_percent"
            ),
        )

    regime_reasons = (
        regime_analysis.get(
            "reasons",
            [],
        )
        or []
    )

    if regime_reasons:

        print("\nREGIME REASONS")

        for reason in regime_reasons:
            print(
                "-",
                reason,
            )

# ============================================================
# VOLUME INTELLIGENCE
# ============================================================

volume_analysis = (
    market_analysis.get(
        "volume",
        {},
    )
    or {}
)

if volume_analysis:

    print("\nVOLUME INTELLIGENCE")
    print("===================")

    print("Bias:", volume_analysis.get("bias"))
    print(
        "Relative Volume:",
        volume_analysis.get("relative_volume"),
    )
    print(
        "Volume Spike:",
        volume_analysis.get("volume_spike"),
    )

    volume_signals = (
        volume_analysis.get("signals", [])
        or []
    )

    if volume_signals:
        print("\nVOLUME SIGNALS")
        for signal in volume_signals:
            print("-", signal)

    volume_reasons = (
        volume_analysis.get("reasons", [])
        or []
    )

    if volume_reasons:
        print("\nVOLUME REASONS")
        for reason in volume_reasons:
            print("-", reason)


# ============================================================
# REGIME-AWARE EVIDENCE
# ============================================================

regime_aware_evidence = (
    market_analysis.get(
        "regime_aware_evidence",
        {},
    )
    or {}
)

if regime_aware_evidence:

    print("\nREGIME-AWARE EVIDENCE")
    print("=====================")

    print(
        "Regime:",
        regime_aware_evidence.get("regime"),
    )
    print(
        "Contextual Bias:",
        regime_aware_evidence.get(
            "contextual_bias"
        ),
    )

    evidence_sections = (
        ("BULLISH EVIDENCE", "bullish_evidence"),
        ("BEARISH EVIDENCE", "bearish_evidence"),
        ("CONFIRMATIONS", "confirmations"),
        ("WARNINGS", "warnings"),
        ("RELEVANT SIGNALS", "relevant_signals"),
    )

    for section_title, section_key in evidence_sections:

        items = (
            regime_aware_evidence.get(
                section_key,
                [],
            )
            or []
        )

        if items:
            print(f"\n{section_title}")
            for item in items:
                print("-", item)


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

    # ========================================================
    # HISTORICAL CONTEXT
    # ========================================================
    #
    # Historical context is advisory only.
    # It is stored inside the opened paper trade metadata
    # and must never override the live decision or safety.
    # ========================================================

    paper_trade = (
        paper_trading_result.get(
            "trade",
            {},
        )
        or {}
    )

    if isinstance(
        paper_trade,
        dict,
    ):

        paper_trade_metadata = (
            paper_trade.get(
                "metadata",
                {},
            )
            or {}
        )

    else:

        paper_trade_metadata = {}

    if isinstance(
        paper_trade_metadata,
        dict,
    ):

        historical_context = (
            paper_trade_metadata.get(
                "historical_context",
                {},
            )
            or {}
        )

    else:

        historical_context = {}

    if (
        isinstance(
            historical_context,
            dict,
        )
        and historical_context
    ):

        print("\nHISTORICAL CONTEXT")
        print("==================")

        print(
            "Historical Bias:",
            historical_context.get(
                "historical_bias"
            ),
        )

        print(
            "Similar Trades:",
            historical_context.get(
                "similar_trades"
            ),
        )

        print(
            "Sufficient Sample:",
            historical_context.get(
                "sufficient_sample"
            ),
        )

        if (
            historical_context.get(
                "win_rate"
            )
            is not None
        ):

            print(
                "Win Rate:",
                historical_context.get(
                    "win_rate"
                ),
            )

        if (
            historical_context.get(
                "expectancy"
            )
            is not None
        ):

            print(
                "Expectancy:",
                historical_context.get(
                    "expectancy"
                ),
            )

        if historical_context.get(
            "reason"
        ):

            print(
                "Reason:",
                historical_context.get(
                    "reason"
                ),
            )

        if historical_context.get(
            "error"
        ):

            print(
                "Historical Context Error:",
                historical_context.get(
                    "error"
                ),
            )

        print(
            "Advisory Only:",
            historical_context.get(
                "advisory_only",
                True,
            ),
        )

        print(
            "Can Override Live Safety:",
            historical_context.get(
                "can_override_live_safety",
                False,
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
