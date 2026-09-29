"""F15-R2.2 evidence-hardening regressions.

These tests capture four evidence defects observed during the live
five-market PAPER audit:

1. NewsEngine runtime dependency must be declared.
2. PreviousDayEngine must accept FYERS epoch candle timestamps.
3. Missing MCX future FULL quote must fail the data-quality gate.
4. Invalid zero future quote must not contaminate Price/OI state.

No credentials.
No network.
No PAPER state writes.
No broker orders.
"""

from __future__ import annotations

import ast
import tomllib
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from mcx.mcx_data_quality import evaluate_all
from mcx.mcx_price_oi import PriceOITracker
from previous_day_engine import PreviousDayEngine


def _requirement_names(path: str) -> set[str]:
    names = set()

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        name = line

        for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if separator in name:
                name = name.split(separator, 1)[0]
                break

        names.add(name.strip().lower())

    return names


def test_news_feedparser_dependency_is_declared_in_runtime_manifests():
    requirements = _requirement_names("requirements.txt")
    runtime_lock = _requirement_names("requirements-runtime-lock.txt")

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    project_dependencies = {
        str(item).split(">=", 1)[0].split("==", 1)[0].strip().lower()
        for item in pyproject["project"]["dependencies"]
    }

    assert "feedparser" in requirements
    assert "feedparser" in runtime_lock
    assert "feedparser-sgmllib" in runtime_lock
    assert "feedparser" in project_dependencies


class EpochHistoryProvider:
    def __init__(self):
        today = datetime.now().date()
        previous = today - timedelta(days=1)

        previous_ts = int(
            datetime.combine(
                previous,
                time(15, 30),
            ).timestamp()
        )

        today_ts = int(
            datetime.combine(
                today,
                time(10, 0),
            ).timestamp()
        )

        self.rows = [
            [
                previous_ts,
                22600.0,
                22800.0,
                22500.0,
                22700.0,
                100000,
            ],
            [
                today_ts,
                22700.0,
                22900.0,
                22600.0,
                22800.0,
                110000,
            ],
        ]

    def getCandleData(self, params):
        return {
            "status": True,
            "data": self.rows,
        }


def test_previous_day_engine_accepts_fyers_epoch_history_timestamp():
    engine = PreviousDayEngine(
        EpochHistoryProvider(),
        market="NIFTY",
        index_exchange="NSE",
        index_token="99926000",
    )

    result = engine.fetch(force=True)

    expected_date = (datetime.now().date() - timedelta(days=1)).isoformat()

    assert result["status"] == "OK"
    assert result["date"] == expected_date
    assert result["open"] == 22600.0
    assert result["high"] == 22800.0
    assert result["low"] == 22500.0
    assert result["close"] == 22700.0


def _good_mcx_evidence():
    now = datetime.now(UTC).isoformat()

    mtf = {
        "status": "OK",
        "timeframes": {
            "5m": {"status": "OK"},
            "15m": {"status": "OK"},
            "1h": {"status": "OK"},
        },
    }

    chain = {
        "status": "OK",
        "future_ltp": 9000.0,
        "ce_data": {
            1: {},
            2: {},
            3: {},
        },
        "pe_data": {
            1: {},
            2: {},
            3: {},
        },
        "fetched_at": now,
    }

    external = {
        "status": "OK",
        "primary": {
            "WTI": {},
        },
        "fetched_at": now,
    }

    session = {
        "status": "OPEN",
        "tradable": True,
    }

    identity = {
        "status": "OK",
        "futures": {
            "symbol": "MCX:TESTFUT",
        },
    }

    return mtf, chain, external, session, identity


def test_mcx_missing_future_quote_fails_data_quality_closed():
    (
        mtf,
        chain,
        external,
        session,
        identity,
    ) = _good_mcx_evidence()

    ok, blockers = evaluate_all(
        mtf=mtf,
        chain=chain,
        external=external,
        session=session,
        identity=identity,
        future_quote=None,
    )

    assert ok is False
    assert "FUTURE_QUOTE_MISSING" in blockers


def test_mcx_omitted_future_quote_preserves_optional_contract():
    (
        mtf,
        chain,
        external,
        session,
        identity,
    ) = _good_mcx_evidence()

    ok, blockers = evaluate_all(
        mtf=mtf,
        chain=chain,
        external=external,
        session=session,
        identity=identity,
    )

    assert ok is True
    assert blockers == []


def test_price_oi_invalid_zero_quote_does_not_replace_valid_baseline():
    tracker = PriceOITracker()

    first = tracker.update(
        8786.0,
        42613,
    )

    assert first["state"] == "UNKNOWN"

    missing = tracker.update(
        0.0,
        0,
    )

    assert missing["state"] == "UNKNOWN"
    assert missing["price_chg_pct"] is None
    assert missing["oi_chg_pct"] is None

    recovered = tracker.update(
        8795.0,
        42750,
    )

    # Recovery must compare against the last VALID quote (8786 / 42613),
    # not against the invalid zero observation.
    assert recovered["price_chg_pct"] is not None
    assert recovered["oi_chg_pct"] is not None
    assert recovered["price_chg_pct"] > 0
    assert recovered["oi_chg_pct"] > 0


def _literal_assignment(path, assignment_name):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))

    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == assignment_name
        ):
            return ast.literal_eval(node.value)

    raise AssertionError(f"{assignment_name} not found in {path}")


def test_r22_policy_epoch_boundary_is_explicit():
    target_tree = ast.parse(Path("src/target_focused_bot.py").read_text(encoding="utf-8"))

    target_values = {}

    for node in target_tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue

        name = node.targets[0].id

        if name in {
            "STRATEGY_VERSION",
            "CERTIFICATION_EPOCH",
        }:
            target_values[name] = ast.literal_eval(node.value)

    assert target_values["STRATEGY_VERSION"] == "NS_DESIGN_B_BID_AUTH_V4"

    assert target_values["CERTIFICATION_EPOCH"] == "NS_CERT_20260929_V4"

    epochs = _literal_assignment(
        "src/mcx/mcx_version.py",
        "PRODUCT_EPOCHS",
    )

    assert epochs["CRUDEOILM"] == {
        "strategy_version": "MCX_POST_PRECISION_V5",
        "epoch": "POST_PRECISION_V5",
        "version_path": "data/paper_trades/mcx_strategy_version.json",
        "certification_eligible": True,
    }

    assert epochs["GOLDM"]["strategy_version"] == "MCX_GOLDM_PRECERT_V3"

    assert epochs["GOLDM"]["epoch"] == "GOLDM_PRECERT_V3"

    assert epochs["GOLDM"]["certification_eligible"] is True

    assert epochs["NATGASMINI"]["strategy_version"] == "MCX_NATGASMINI_PRECERT_V2"

    assert epochs["NATGASMINI"]["epoch"] == "NATGASMINI_PRECERT_V2"

    assert epochs["NATGASMINI"]["certification_eligible"] is True


def test_readonly_preflight_index_authority_matches_runtime_policy():
    runtime_strategy = _literal_assignment(
        "src/target_focused_bot.py",
        "STRATEGY_VERSION",
    )

    runtime_epoch = _literal_assignment(
        "src/target_focused_bot.py",
        "CERTIFICATION_EPOCH",
    )

    preflight_strategy = _literal_assignment(
        "services/paper_orchestration/state_authority_readonly_v2.py",
        "INDEX_STRATEGY_VERSION",
    )

    preflight_epoch = _literal_assignment(
        "services/paper_orchestration/state_authority_readonly_v2.py",
        "INDEX_CERTIFICATION_EPOCH",
    )

    assert runtime_strategy == "NS_DESIGN_B_BID_AUTH_V4"

    assert runtime_epoch == "NS_CERT_20260929_V4"

    assert preflight_strategy == runtime_strategy

    assert preflight_epoch == runtime_epoch


# E9R_R22_OPERATIONAL_RELIABILITY_TESTS


def test_r22_clean_session_end_is_latched_until_next_day(
    tmp_path,
    monkeypatch,
):
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from services.paper_orchestration import (
        automated_paper_supervisor_v2 as supervisor_module,
    )
    from services.paper_orchestration.automated_paper_supervisor_v2 import (
        AutomatedPaperSupervisorV2,
        StartOutcome,
    )
    from services.paper_orchestration.certification_halt_v2 import (
        MarketState,
    )
    from services.paper_orchestration.worker_session_authority_v2 import (
        SessionAuthority,
    )

    ist = ZoneInfo(
        "Asia/Kolkata"
    )

    class Clock:
        def __init__(self, now):
            self.now = now

        def __call__(self):
            return self.now

    class Process:
        def __init__(
            self,
            rc=None,
        ):
            self.rc = rc
            self.pid = 424242

        def poll(self):
            return self.rc

    t0 = datetime(
        2026,
        9,
        29,
        15,
        28,
        30,
        tzinfo=ist,
    )

    clock = Clock(
        t0
    )

    supervisor = AutomatedPaperSupervisorV2(
        repo_root=str(
            tmp_path
        ),
        python_exe="python",
        dry_run=False,
        log_dir="logs/supervisor",
        clock=clock,
        markets=(
            "NIFTY",
        ),
    )

    monkeypatch.setattr(
        supervisor_module,
        "_cert_all_complete",
        lambda: False,
    )

    monkeypatch.setattr(
        supervisor_module,
        "_cert_market_state",
        lambda name: MarketState(
            name,
            "VALID_COUNTER",
            0,
        ),
    )

    authority = SessionAuthority(
        True,
        True,
        True,
        None,
        True,
        "OPEN",
        "",
    )

    monkeypatch.setattr(
        supervisor_module,
        "_session_authority_for",
        lambda spec, now: authority,
    )

    analysis_days = []

    monkeypatch.setattr(
        supervisor,
        "_run_analysis_and_record",
        lambda rt, spec, day:
            analysis_days.append(
                day
            )
            or "ANALYSIS_SUCCESS",
    )

    starts = []

    def fake_start(spec):
        starts.append(
            spec.name
        )

        return StartOutcome(
            "STARTED",
            process=Process(
                rc=None
            ),
        )

    monkeypatch.setattr(
        supervisor,
        "_start_worker",
        fake_start,
    )

    runtime = supervisor.workers[
        "NIFTY"
    ]

    runtime.process = Process(
        rc=0
    )

    runtime.last_start_ist = (
        t0
    )

    supervisor.tick()

    assert (
        runtime.last_exit_status
        == "CLEAN_SESSION_END"
    )

    assert (
        runtime.session_end_latched_date
        == date(
            2026,
            9,
            29,
        )
    )

    assert starts == []

    clock.now = datetime(
        2026,
        9,
        29,
        15,
        29,
        15,
        tzinfo=ist,
    )

    supervisor.tick()

    assert starts == []

    assert (
        runtime.session_end_latched_date
        == date(
            2026,
            9,
            29,
        )
    )

    # New authoritative day clears the latch and permits a fresh worker.
    clock.now = datetime(
        2026,
        9,
        30,
        9,
        20,
        0,
        tzinfo=ist,
    )

    supervisor.tick()

    assert (
        runtime.session_end_latched_date
        is None
    )

    assert starts == [
        "NIFTY",
    ]


def test_r22_mcx_state_replace_retries_transient_permission_error(
    tmp_path,
    monkeypatch,
):
    import json

    from mcx import mcx_paper_bot

    monkeypatch.setattr(
        mcx_paper_bot,
        "PRODUCT",
        "CRUDEOILM",
    )

    state_path = (
        tmp_path
        / "mcx_crudeoilm_experimental.json"
    )

    monkeypatch.setattr(
        mcx_paper_bot,
        "STATE_PATH",
        str(
            state_path
        ),
    )

    state = (
        mcx_paper_bot._default_state_for(
            "CRUDEOILM"
        )
    )

    real_replace = (
        mcx_paper_bot.os.replace
    )

    calls = {
        "count": 0,
    }

    def flaky_replace(
        source,
        target,
    ):
        calls[
            "count"
        ] += 1

        if calls["count"] <= 2:
            raise PermissionError(
                13,
                "simulated transient Windows lock",
            )

        return real_replace(
            source,
            target,
        )

    monkeypatch.setattr(
        mcx_paper_bot.os,
        "replace",
        flaky_replace,
    )

    monkeypatch.setattr(
        mcx_paper_bot.time,
        "sleep",
        lambda seconds: None,
    )

    mcx_paper_bot.save_state(
        state
    )

    assert calls["count"] == 3

    durable = json.loads(
        state_path.read_text(
            encoding="utf-8",
        )
    )

    assert (
        durable["product"]
        == "CRUDEOILM"
    )

    assert (
        durable["strategy_version"]
        == state["strategy_version"]
    )

    assert (
        durable["epoch"]
        == state["epoch"]
    )


def test_r22_mcx_state_replace_exhaustion_remains_fail_closed(
    tmp_path,
    monkeypatch,
):
    import json

    from mcx import mcx_paper_bot

    monkeypatch.setattr(
        mcx_paper_bot,
        "PRODUCT",
        "CRUDEOILM",
    )

    state_path = (
        tmp_path
        / "mcx_crudeoilm_experimental.json"
    )

    monkeypatch.setattr(
        mcx_paper_bot,
        "STATE_PATH",
        str(
            state_path
        ),
    )

    old_state = (
        mcx_paper_bot._default_state_for(
            "CRUDEOILM"
        )
    )

    state_path.write_text(
        json.dumps(
            old_state,
        ),
        encoding="utf-8",
    )

    before = (
        state_path.read_bytes()
    )

    new_state = dict(
        old_state
    )

    new_state[
        "total_trades"
    ] = 99

    calls = {
        "count": 0,
    }

    def always_locked(
        source,
        target,
    ):
        calls[
            "count"
        ] += 1

        raise PermissionError(
            13,
            "simulated persistent Windows lock",
        )

    monkeypatch.setattr(
        mcx_paper_bot.os,
        "replace",
        always_locked,
    )

    monkeypatch.setattr(
        mcx_paper_bot.time,
        "sleep",
        lambda seconds: None,
    )

    raised = None

    try:
        mcx_paper_bot.save_state(
            new_state
        )

    except (
        mcx_paper_bot.MCXStateAuthorityError
    ) as exc:
        raised = exc

    assert raised is not None

    assert (
        str(
            raised
        )
        == "STATE_WRITE_FAILED"
    )

    assert (
        calls["count"]
        == mcx_paper_bot._STATE_REPLACE_MAX_ATTEMPTS
    )

    # Atomic contract: previous durable state survives.
    assert (
        state_path.read_bytes()
        == before
    )

    # Temporary state file must be cleaned.
    leftovers = [
        path
        for path in tmp_path.iterdir()
        if path.name.endswith(
            ".tmp"
        )
    ]

    assert leftovers == []


def test_r22_heartbeat_retries_transient_permission_error(
    tmp_path,
    monkeypatch,
):
    import json

    from services.paper_orchestration import (
        worker_heartbeat_v2,
    )

    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(
            tmp_path
        ),
    )

    real_replace = (
        worker_heartbeat_v2.os.replace
    )

    calls = {
        "count": 0,
    }

    def flaky_replace(
        source,
        target,
    ):
        calls[
            "count"
        ] += 1

        if calls["count"] <= 2:
            raise PermissionError(
                13,
                "simulated transient Windows lock",
            )

        return real_replace(
            source,
            target,
        )

    monkeypatch.setattr(
        worker_heartbeat_v2.os,
        "replace",
        flaky_replace,
    )

    monkeypatch.setattr(
        worker_heartbeat_v2.time,
        "sleep",
        lambda seconds: None,
    )

    worker_heartbeat_v2.beat(
        "CRUDEOILM",
        "SLEEP",
        cycle_number=99,
        has_active_position=True,
        trade_id="TEST_OPEN",
    )

    assert calls["count"] == 3

    payload = json.loads(
        (
            tmp_path
            / "CRUDEOILM.json"
        ).read_text(
            encoding="utf-8",
        )
    )

    assert (
        payload["cycle_number"]
        == 99
    )

    assert (
        payload["has_active_position"]
        is True
    )

    assert (
        payload["trade_id"]
        == "TEST_OPEN"
    )
