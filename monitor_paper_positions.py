"""
Standalone Live Paper Position Monitor.

Flow:
1. Check the Indian market session.
2. Stop before broker access when the market is closed.
3. Create and authenticate the Angel One market-data client.
4. Recover persisted paper trades.
5. Fetch live option LTPs for open paper positions.
6. Update paper P&L.
7. Allow the paper-trading engine to auto-close SL/target hits.
8. Print a structured monitoring report.

IMPORTANT:
- PAPER TRADING ONLY.
- MARKET-DATA ACCESS ONLY.
- NO REAL ORDER PLACEMENT.
"""

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.live_paper_position_monitor import (
    LivePaperPositionMonitor,
)

from services.market_session_guard import (
    evaluate_market_session,
)

from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)


MAXIMUM_CANDLE_AGE_MINUTES = 10

DEFAULT_OPTION_EXCHANGE = "NFO"

ENFORCE_MARKET_SESSION = True


def print_header():
    print("\n================================")
    print("AI TRADING COPILOT")
    print("LIVE PAPER POSITION MONITOR")
    print("================================")

    print(
        "\nMode: PAPER TRADING ONLY"
    )

    print(
        "Option Exchange:",
        DEFAULT_OPTION_EXCHANGE,
    )

    print(
        "Market Session Enforcement:",
        ENFORCE_MARKET_SESSION,
    )


def check_market_session():
    """
    Evaluate whether live monitoring is allowed.

    Returns
    -------
    dict
        Market-session result.
    """

    if not ENFORCE_MARKET_SESSION:
        return {
            "status": "SESSION_CHECK_DISABLED",
            "allowed": True,
            "market_open": True,
            "reasons": [],
        }

    return evaluate_market_session(
        maximum_candle_age_minutes=(
            MAXIMUM_CANDLE_AGE_MINUTES
        ),
        holiday_calendar=(
            get_nse_holiday_calendar()
        ),
    )


def print_market_session(
    session,
):
    print("\nMARKET SESSION")
    print("==============")

    print(
        "Status:",
        session.get(
            "status"
        ),
    )

    print(
        "Allowed:",
        session.get(
            "allowed"
        ),
    )

    print(
        "Market Open:",
        session.get(
            "market_open"
        ),
    )

    print(
        "Trading Weekday:",
        session.get(
            "is_weekday"
        ),
    )

    print(
        "Market Holiday:",
        session.get(
            "is_market_holiday"
        ),
    )

    print(
        "Within Market Hours:",
        session.get(
            "within_market_hours"
        ),
    )

    print(
        "Current Time:",
        session.get(
            "current_time"
        ),
    )

    reasons = (
        session.get(
            "reasons",
            [],
        )
        or []
    )

    if reasons:
        print("\nSESSION REASONS")

        for reason in reasons:
            print(
                "-",
                reason,
            )


def print_monitoring_report(
    report,
):
    print("\nPAPER POSITION MONITORING REPORT")
    print("================================")

    print(
        "Status:",
        report.get(
            "status"
        ),
    )

    print(
        "Recovery Performed:",
        report.get(
            "recovery_performed"
        ),
    )

    print(
        "Recovered Trades:",
        report.get(
            "recovered_trade_count"
        ),
    )

    print(
        "Open Trades Found:",
        report.get(
            "open_trades_found"
        ),
    )

    print(
        "Successfully Processed:",
        report.get(
            "processed"
        ),
    )

    print(
        "Failed:",
        report.get(
            "failed"
        ),
    )

    print(
        "Open Trades After:",
        report.get(
            "open_trades_after"
        ),
    )

    print(
        "Closed Trades After:",
        report.get(
            "closed_trades_after"
        ),
    )

    print(
        "Updated At:",
        report.get(
            "updated_at"
        ),
    )

    results = (
        report.get(
            "results",
            [],
        )
        or []
    )

    if not results:
        print(
            "\nNo open paper positions required updating."
        )

        return

    print("\nPOSITION RESULTS")
    print("================")

    for result in results:
        print(
            "\nTrade ID:",
            result.get(
                "trade_id"
            ),
        )

        print(
            "Status:",
            result.get(
                "status"
            ),
        )

        print(
            "Current Price:",
            result.get(
                "current_price"
            ),
        )

        error = result.get(
            "error"
        )

        if error:
            print(
                "Error:",
                error,
            )

        trade = result.get(
            "trade"
        )

        if isinstance(
            trade,
            dict,
        ):
            print(
                "Position Status:",
                trade.get(
                    "status"
                ),
            )

            print(
                "Option Symbol:",
                trade.get(
                    "option_symbol"
                ),
            )

            print(
                "Entry Price:",
                trade.get(
                    "entry_price"
                ),
            )

            print(
                "Stop Loss:",
                trade.get(
                    "stop_loss_price"
                ),
            )

            print(
                "Target:",
                trade.get(
                    "target_price"
                ),
            )

            print(
                "Unrealized P&L:",
                trade.get(
                    "unrealized_pnl"
                ),
            )

            print(
                "Realized P&L:",
                trade.get(
                    "realized_pnl"
                ),
            )

            print(
                "Exit Price:",
                trade.get(
                    "exit_price"
                ),
            )

            print(
                "Exit Reason:",
                trade.get(
                    "exit_reason"
                ),
            )


def main(
    *,
    client_factory=AngelMarketDataClient,
    monitor_factory=LivePaperPositionMonitor,
    session_checker=check_market_session,
):
    """
    Run one live paper-position monitoring cycle.

    Dependencies are injectable for testing.

    Returns
    -------
    int
        Process-style exit code.
    """

    print_header()

    # --------------------------------------------------------
    # MARKET SESSION SAFETY GATE
    # --------------------------------------------------------

    try:
        session = (
            session_checker()
        )

    except Exception as exc:
        print("\n================================")
        print("MARKET SESSION ERROR")
        print("================================")

        print(
            "Unable to verify the market session."
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "\nNo broker market-data request was made."
        )

        print(
            "No paper position was updated."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    if not isinstance(
        session,
        dict,
    ):
        print("\n================================")
        print("MARKET SESSION ERROR")
        print("================================")

        print(
            "Market-session check returned invalid data."
        )

        print(
            "No broker market-data request was made."
        )

        print(
            "No paper position was updated."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    print_market_session(
        session
    )

    if (
        ENFORCE_MARKET_SESSION
        and not session.get(
            "market_open",
            False,
        )
    ):
        print("\n================================")
        print("MONITORING SKIPPED")
        print("================================")

        print(
            "The market is currently closed."
        )

        print(
            "No Angel One login was attempted."
        )

        print(
            "No live option prices were requested."
        )

        print(
            "No paper positions were updated."
        )

        print(
            "\nPAPER TRADING ONLY"
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 0

    # --------------------------------------------------------
    # CREATE MARKET-DATA CLIENT
    # --------------------------------------------------------

    try:
        client = (
            client_factory()
        )

    except Exception as exc:
        print("\n================================")
        print("BROKER CLIENT ERROR")
        print("================================")

        print(
            "Unable to create the Angel One "
            "market-data client."
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "No paper positions were updated."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    try:
        client.login()

    except Exception as exc:
        print("\n================================")
        print("BROKER LOGIN ERROR")
        print("================================")

        print(
            "Unable to authenticate the "
            "Angel One market-data client."
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "No live option prices were requested."
        )

        print(
            "No paper positions were updated."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    # --------------------------------------------------------
    # CREATE MONITOR
    # --------------------------------------------------------

    try:
        monitor = (
            monitor_factory(
                market_data_client=(
                    client
                ),
                default_option_exchange=(
                    DEFAULT_OPTION_EXCHANGE
                ),
                recover_on_start=True,
            )
        )

    except Exception as exc:
        print("\n================================")
        print("MONITOR INITIALIZATION ERROR")
        print("================================")

        print(
            "Unable to initialize the live "
            "paper-position monitor."
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "No paper positions were updated."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    # --------------------------------------------------------
    # RUN ONE MONITORING CYCLE
    # --------------------------------------------------------

    try:
        report = (
            monitor.run_once()
        )

    except Exception as exc:
        print("\n================================")
        print("MONITORING ERROR")
        print("================================")

        print(
            "The paper-position monitoring cycle "
            "could not complete."
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "Any successfully persisted paper-trade "
            "updates remain controlled by the "
            "paper-trading engine."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    if not isinstance(
        report,
        dict,
    ):
        print("\n================================")
        print("MONITORING ERROR")
        print("================================")

        print(
            "The monitor returned an invalid report."
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print_monitoring_report(
        report
    )

    print("\n================================")
    print("MONITORING COMPLETE")
    print("================================")

    print(
        "PAPER TRADING ONLY"
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )

    if (
        report.get(
            "status"
        )
        == "COMPLETED_WITH_ERRORS"
    ):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )