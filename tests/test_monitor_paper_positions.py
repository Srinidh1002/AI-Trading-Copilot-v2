import monitor_paper_positions as entry


# ============================================================
# FAKES
# ============================================================


class FakeClient:

    def __init__(
        self,
        login_error=None,
    ):
        self.login_error = (
            login_error
        )

        self.login_calls = 0

    def login(
        self,
        force=False,
    ):
        self.login_calls += 1

        if self.login_error:
            raise self.login_error

        return {
            "status": True
        }


class FakeMonitor:

    def __init__(
        self,
        report=None,
        error=None,
    ):
        self.report = (
            report
            if report is not None
            else make_report()
        )

        self.error = error

        self.run_calls = 0

    def run_once(
        self,
    ):
        self.run_calls += 1

        if self.error:
            raise self.error

        return self.report


def open_session():
    return {
        "status": "MARKET_OPEN",
        "allowed": True,
        "market_open": True,
        "is_weekday": True,
        "is_market_holiday": False,
        "within_market_hours": True,
        "current_time": (
            "2026-07-13T10:00:00+05:30"
        ),
        "reasons": [],
    }


def closed_session():
    return {
        "status": "MARKET_CLOSED",
        "allowed": False,
        "market_open": False,
        "is_weekday": False,
        "is_market_holiday": False,
        "within_market_hours": False,
        "current_time": (
            "2026-07-12T19:45:00+05:30"
        ),
        "reasons": [
            "Market is closed."
        ],
    }


def make_report(
    status="COMPLETED",
):
    return {
        "status": status,
        "recovery_performed": True,
        "recovered_trade_count": 2,
        "open_trades_found": 1,
        "processed": 1,
        "failed": 0,
        "open_trades_after": 1,
        "closed_trades_after": 1,
        "updated_at": (
            "2026-07-13T10:00:00+00:00"
        ),
        "results": [],
    }


# ============================================================
# HEADER / SESSION
# ============================================================


def test_print_header(
    capsys,
):
    entry.print_header()

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "LIVE PAPER POSITION MONITOR"
        in output
    )

    assert (
        "PAPER TRADING ONLY"
        in output
    )


def test_closed_market_returns_zero(
    capsys,
):
    client_created = {
        "value": False
    }

    def client_factory():
        client_created[
            "value"
        ] = True

        return FakeClient()

    result = entry.main(
        client_factory=(
            client_factory
        ),
        session_checker=(
            closed_session
        ),
    )

    assert result == 0

    assert (
        client_created[
            "value"
        ]
        is False
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "MONITORING SKIPPED"
        in output
    )


def test_closed_market_does_not_login():

    client = (
        FakeClient()
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        session_checker=(
            closed_session
        ),
    )

    assert result == 0

    assert (
        client.login_calls
        == 0
    )


def test_session_exception_returns_one():

    def failing_session():
        raise RuntimeError(
            "Session failure"
        )

    result = entry.main(
        session_checker=(
            failing_session
        ),
    )

    assert result == 1


def test_invalid_session_result_returns_one():

    result = entry.main(
        session_checker=(
            lambda: None
        ),
    )

    assert result == 1


# ============================================================
# CLIENT / LOGIN
# ============================================================


def test_open_market_creates_client():

    created = {
        "value": False
    }

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    def client_factory():
        created[
            "value"
        ] = True

        return client

    result = entry.main(
        client_factory=(
            client_factory
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 0

    assert (
        created[
            "value"
        ]
        is True
    )


def test_open_market_logs_in():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert (
        client.login_calls
        == 1
    )


def test_client_creation_failure_returns_one():

    def failing_factory():
        raise RuntimeError(
            "Client failure"
        )

    result = entry.main(
        client_factory=(
            failing_factory
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


def test_login_failure_returns_one():

    client = (
        FakeClient(
            login_error=RuntimeError(
                "Login failed"
            )
        )
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


# ============================================================
# MONITOR CREATION
# ============================================================


def test_monitor_receives_client():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    received = {}

    def monitor_factory(
        **kwargs,
    ):
        received.update(
            kwargs
        )

        return monitor

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            monitor_factory
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 0

    assert (
        received[
            "market_data_client"
        ]
        is client
    )


def test_monitor_receives_nfo_exchange():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    received = {}

    def monitor_factory(
        **kwargs,
    ):
        received.update(
            kwargs
        )

        return monitor

    entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            monitor_factory
        ),
        session_checker=(
            open_session
        ),
    )

    assert (
        received[
            "default_option_exchange"
        ]
        == "NFO"
    )


def test_monitor_enables_recovery():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    received = {}

    def monitor_factory(
        **kwargs,
    ):
        received.update(
            kwargs
        )

        return monitor

    entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            monitor_factory
        ),
        session_checker=(
            open_session
        ),
    )

    assert (
        received[
            "recover_on_start"
        ]
        is True
    )


def test_monitor_creation_failure_returns_one():

    client = (
        FakeClient()
    )

    def failing_monitor_factory(
        **kwargs,
    ):
        raise RuntimeError(
            "Monitor creation failed"
        )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            failing_monitor_factory
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


# ============================================================
# MONITOR RUN
# ============================================================


def test_monitor_runs_once():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 0

    assert (
        monitor.run_calls
        == 1
    )


def test_monitor_failure_returns_one():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor(
            error=RuntimeError(
                "Monitoring failed"
            )
        )
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


def test_invalid_monitor_report_returns_one():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor(
            report=[
                "invalid"
            ]
        )
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


def test_completed_with_errors_returns_one():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor(
            report=make_report(
                status=(
                    "COMPLETED_WITH_ERRORS"
                )
            )
        )
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 1


def test_completed_returns_zero():

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor(
            report=make_report(
                status="COMPLETED"
            )
        )
    )

    result = entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    assert result == 0


# ============================================================
# REPORT OUTPUT
# ============================================================


def test_report_prints_counts(
    capsys,
):

    entry.print_monitoring_report(
        make_report()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Recovered Trades: 2"
        in output
    )

    assert (
        "Open Trades Found: 1"
        in output
    )

    assert (
        "Successfully Processed: 1"
        in output
    )


def test_empty_results_message(
    capsys,
):

    entry.print_monitoring_report(
        make_report()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "No open paper positions required updating."
        in output
    )


def test_report_prints_trade_result(
    capsys,
):

    report = (
        make_report()
    )

    report[
        "results"
    ] = [
        {
            "trade_id": "paper-1",
            "status": "PROCESSED",
            "current_price": 125.0,
            "error": None,
            "trade": {
                "status": "OPEN",
                "option_symbol": (
                    "NIFTY26JUL25000CE"
                ),
                "entry_price": 100.0,
                "stop_loss_price": 80.0,
                "target_price": 140.0,
                "unrealized_pnl": 1875.0,
                "realized_pnl": None,
                "exit_price": None,
                "exit_reason": None,
            },
        }
    ]

    entry.print_monitoring_report(
        report
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Trade ID: paper-1"
        in output
    )

    assert (
        "Current Price: 125.0"
        in output
    )

    assert (
        "NIFTY26JUL25000CE"
        in output
    )


def test_report_prints_error(
    capsys,
):

    report = (
        make_report()
    )

    report[
        "results"
    ] = [
        {
            "trade_id": "paper-1",
            "status": "ERROR",
            "current_price": None,
            "trade": None,
            "error": (
                "Price unavailable"
            ),
        }
    ]

    entry.print_monitoring_report(
        report
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Price unavailable"
        in output
    )


def test_success_footer_confirms_no_real_order(
    capsys,
):

    client = (
        FakeClient()
    )

    monitor = (
        FakeMonitor()
    )

    entry.main(
        client_factory=(
            lambda: client
        ),
        monitor_factory=(
            lambda **kwargs: monitor
        ),
        session_checker=(
            open_session
        ),
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "NO REAL ORDER WAS PLACED"
        in output
    )