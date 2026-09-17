"""Focused Task 9.25 tests for the zero-REST capture-boundary fallback."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_live_paper_certification_launcher import (
    Task9ExternalProviderBlockedError,
    Task9LivePaperCertificationLauncher,
    Task9LivePaperRunManifestV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.market.task9_historical_websocket_composition import (
    REQUIRED_TIMEFRAMES,
    build_task9_precomposed_timeframe_provider,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_runtime_composition import (
    capture_certified_live_evidence,
)


IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 8, 11, 13, 15, tzinfo=IST)


def _session_resolver(
    *,
    market,
    evaluated_at,
    market_date,
):
    from datetime import time

    from services.contracts.task9_market_session_policy_v1 import (
        Task9MarketSegment,
        Task9SessionPhase,
    )
    from services.contracts.task9_market_session_state_v1 import (
        Task9SegmentSessionStateV1,
    )

    return Task9SegmentSessionStateV1(
        segment=(
            Task9MarketSegment.NFO_OPTIONS
            if market == "NIFTY"
            else Task9MarketSegment.BFO_OPTIONS
        ),
        market_date=market_date,
        evaluated_at=evaluated_at,
        timezone="Asia/Kolkata",
        phase=Task9SessionPhase.OPEN,
        market_open=True,
        new_entries_allowed=True,
        position_monitoring_allowed=True,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task925-session-policy",
        policy_version="1",
    )


def _write_valid_startup_preflight(root):
    from services.certification.task9_startup_preflight_store import (
        Task9StartupPreflightStore,
    )
    from services.contracts.task9_startup_preflight_v1 import (
        Task9StartupPreflightPhase,
        Task9StartupPreflightPhaseResultV1,
        Task9StartupPreflightPhaseStatus,
        Task9StartupPreflightResultV1,
    )

    sha = "a" * 64

    receipt = Task9StartupPreflightResultV1(
        preflight_id="task9102-preflight",
        runtime_config_snapshot_id=(
            "task9-runtime-config-" + sha
        ),
        runtime_config_sha256=sha,
        campaign_id="task9102-campaign",
        market_date=AS_OF.date(),
        official_run_id="task925-run",
        run_classification="OFFICIAL_CERTIFICATION",
        started_at=AS_OF,
        completed_at=AS_OF,
        phase_results=tuple(
            Task9StartupPreflightPhaseResultV1(
                phase,
                Task9StartupPreflightPhaseStatus.PASS,
                False,
                "TASK9102_TEST_PASS",
                None,
                AS_OF,
            )
            for phase in Task9StartupPreflightPhase
        ),
    )

    Task9StartupPreflightStore(
        root
    ).save(receipt)


def _cycle(*, symbol="NIFTY", exchange="NSE"):
    policy = PaperOrchestrationPolicyV1(
        orchestration_policy_id="task925-test-policy",
        policy_timestamp=AS_OF,
    )
    session = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=AS_OF,
        evaluated_at=AS_OF + timedelta(seconds=1),
        id_factory=lambda: f"task925-session-{symbol}",
    )
    return build_certified_cycle_input(
        cycle_kind="OPPORTUNITY",
        observation_id=f"task925-{symbol}",
        orchestration_policy=policy,
        underlying_symbol=symbol,
        exchange=exchange,
        market_timestamp=AS_OF,
        received_at=AS_OF + timedelta(seconds=1),
        cycle_requested_at=AS_OF + timedelta(seconds=2),
        session_validation=session,
        metadata={
            "spot_price": 25000.0,
            "captured_spot_payload": {"spot_price": 25000.0},
        },
    )


def _captured_rows():
    return {
        "rows_by_timeframe": {
            timeframe: (("2026-08-10T09:15:00+05:30", 1, 2, 1, 2, 10),)
            for timeframe in REQUIRED_TIMEFRAMES
        },
        "dataframes": {timeframe: object() for timeframe in REQUIRED_TIMEFRAMES},
        "cache_metadata": {timeframe: {"captured": True} for timeframe in REQUIRED_TIMEFRAMES},
        "request_diagnostics": {"5m": {"provider_attempted": False}},
    }


class _OptionPipeline:
    def __init__(self):
        self.calls = []

    def capture_option_inputs(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            contracts=({"symbol": "NIFTYTEST"},),
            blockers=(),
            warnings=(),
            metadata={"source": "normal-option-capture"},
        )


def test_capture_normal_path_uses_existing_fetch_and_preserves_evidence_contract():
    data_service = SimpleNamespace(fetch_all_with_capture=Mock(return_value=_captured_rows()))
    options = _OptionPipeline()

    cycle = _cycle()
    evidence = capture_certified_live_evidence(
        cycle_input=cycle, data_service=data_service,
        option_decision_pipeline=options,
        precomposed_timeframe_provider=None,
    )

    data_service.fetch_all_with_capture.assert_called_once_with("NSE", "99926000", end_time=AS_OF)
    assert tuple(evidence.candle_rows_by_timeframe) == REQUIRED_TIMEFRAMES
    assert evidence.cache_metadata["candles"]["5m"]["captured"] is True
    assert evidence.provider_timestamp == AS_OF
    assert cycle.execution_mode == "PAPER"
    assert cycle.metadata["broker_order_submission"] is False
    assert cycle.metadata["live_execution_eligible"] is False


def test_injected_timeframe_provider_skips_historical_fetch_but_preserves_normal_capture():
    data_service = SimpleNamespace(fetch_all_with_capture=Mock(side_effect=AssertionError("REST must not run")))
    options = _OptionPipeline()
    provider = Mock(return_value=_captured_rows())

    cycle = _cycle()
    evidence = capture_certified_live_evidence(
        cycle_input=cycle, data_service=data_service,
        option_decision_pipeline=options,
        precomposed_timeframe_provider=provider,
    )

    data_service.fetch_all_with_capture.assert_not_called()
    provider.assert_called_once_with(exchange="NSE", symboltoken="99926000", end_time=AS_OF)
    assert len(options.calls) == 1
    assert options.calls[0]["provider_timestamp"] == AS_OF
    assert options.calls[0]["evaluated_at"] == AS_OF + timedelta(seconds=1)
    assert evidence.option_contracts == ({"symbol": "NIFTYTEST"},)
    assert evidence.cache_metadata["request_diagnostics"] == {"5m": {"provider_attempted": False}}
    assert evidence.provider_blockers == ()
    assert cycle.execution_mode == "PAPER"
    assert cycle.metadata["broker_order_submission"] is False
    assert cycle.metadata["live_execution_eligible"] is False


class _CacheOnly:
    def __init__(self, *, missing=(), missing_by_exchange=None):
        self.missing = set(missing)
        self.missing_by_exchange = {
            key: set(value) for key, value in (missing_by_exchange or {}).items()
        }
        self.calls = []

    def get_incremental_candidate(self, exchange, symboltoken, timeframe):
        self.calls.append((exchange, symboltoken, timeframe))
        if timeframe in self.missing or timeframe in self.missing_by_exchange.get(exchange, set()):
            return None
        start = {
            "5m": "2026-08-11T13:10:00+05:30",
            "15m": "2026-08-11T13:00:00+05:30",
            "1h": "2026-08-11T12:15:00+05:30",
            "1d": "2026-08-10T00:00:00+05:30",
        }[timeframe]
        return {"response": {"data": [[start, 1, 2, 1, 2, 10]]}}


def _local_provider(tmp_path, *, missing=()):
    cache = _CacheOnly(missing=missing)
    provider = build_task9_precomposed_timeframe_provider(
        live_stream_root=tmp_path / "live_stream",
        session_state_resolver=_session_resolver,
    )(SimpleNamespace(cache=cache))
    return provider, cache


def test_local_provider_has_exact_capture_schema_and_is_restart_deterministic(tmp_path):
    provider, cache = _local_provider(tmp_path)
    first = provider(exchange="NSE", symboltoken="99926000", end_time=AS_OF)
    restarted, restarted_cache = _local_provider(tmp_path)
    second = restarted(exchange="NSE", symboltoken="99926000", end_time=AS_OF)

    assert tuple(first) == ("rows_by_timeframe", "dataframes", "cache_metadata", "request_diagnostics")
    assert first == second
    assert tuple(first["rows_by_timeframe"]) == REQUIRED_TIMEFRAMES
    assert all(item["local_composed"] is True for item in first["cache_metadata"].values())
    assert len(cache.calls) == len(restarted_cache.calls) == 4


def test_local_provider_fails_closed_for_missing_mandatory_5m_before_rest(tmp_path):
    missing = "5m"
    provider, cache = _local_provider(tmp_path, missing=(missing,))

    with pytest.raises(ValueError, match=f"TASK9_LOCAL_EVIDENCE_UNAVAILABLE_NIFTY_{missing}"):
        provider(exchange="NSE", symboltoken="99926000", end_time=AS_OF)

    assert cache.calls == [("NSE", "99926000", timeframe) for timeframe in REQUIRED_TIMEFRAMES[:REQUIRED_TIMEFRAMES.index(missing) + 1]]


def test_local_provider_omits_missing_optional_timeframes_with_typed_warnings(tmp_path):
    provider, cache = _local_provider(tmp_path, missing=("1h", "1d"))

    result = provider(exchange="NSE", symboltoken="99926000", end_time=AS_OF)

    assert tuple(result["rows_by_timeframe"]) == ("5m", "15m")
    assert result["cache_metadata"]["1h"]["warning"] == "optional_timeframe_unavailable_1h"
    assert result["cache_metadata"]["1d"]["warning"] == "optional_timeframe_unavailable_1d"
    assert cache.calls == [("NSE", "99926000", timeframe) for timeframe in REQUIRED_TIMEFRAMES]


def test_optional_local_capture_failures_are_handoff_warnings_not_provider_blockers(tmp_path):
    provider, _ = _local_provider(tmp_path, missing=("1h", "1d"))
    evidence = capture_certified_live_evidence(
        cycle_input=_cycle(),
        data_service=SimpleNamespace(fetch_all_with_capture=Mock(side_effect=AssertionError("REST must not run"))),
        option_decision_pipeline=_OptionPipeline(),
        precomposed_timeframe_provider=provider,
    )

    assert evidence.provider_blockers == ()
    assert evidence.provider_warnings == (
        "optional_timeframe_unavailable_1h",
        "optional_timeframe_unavailable_1d",
    )


def test_local_provider_keeps_nifty_and_sensex_readiness_independent(tmp_path):
    cache = _CacheOnly(missing_by_exchange={"BSE": ("1h",)})
    provider = build_task9_precomposed_timeframe_provider(
        live_stream_root=tmp_path / "live_stream",
        session_state_resolver=_session_resolver,
    )(SimpleNamespace(cache=cache))

    nifty = provider(exchange="NSE", symboltoken="99926000", end_time=AS_OF)
    sensex = provider(exchange="BSE", symboltoken="99919000", end_time=AS_OF)

    assert tuple(nifty["rows_by_timeframe"]) == REQUIRED_TIMEFRAMES
    assert tuple(sensex["rows_by_timeframe"]) == ("5m", "15m", "1d")
    assert sensex["cache_metadata"]["1h"]["warning"] == "optional_timeframe_unavailable_1h"


def test_active_typed_rate_limit_selects_fallback_without_mutating_blocker(tmp_path):
    _write_valid_startup_preflight(tmp_path)

    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path, official_run_id="task925-run",
            startup_preflight_id="task9102-preflight",
            runtime_config_snapshot_id="task9-runtime-config-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            runtime_config_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            campaign_id="task9102-campaign",
            market_date=AS_OF.date(),
        task9_evidence_dependencies_factory=lambda **_: None,
        runtime_factory=lambda **_: None, clock=lambda: AS_OF,
        sleep=lambda _: None,
        session_state_resolver=_session_resolver,
    )
    active = {
        "status": "ACTIVE", "provider": "ANGEL_ONE", "endpoint": "historical-data",
        "last_failure_reason": "HISTORICAL-DATA_RATE_LIMITED",
        "next_probe_not_before": (AS_OF + timedelta(hours=1)).isoformat(),
        "blocker_code": "EXTERNAL_PROVIDER_CLIENT_CODE_QUOTA_STATE",
    }
    store = SimpleNamespace(load=Mock(return_value=active))
    selected = []
    manifest = Task9LivePaperRunManifestV1("task925-run", AS_OF)
    lock = SimpleNamespace(acquire=lambda: None, release=lambda: None)
    with patch("services.certification.task9_live_paper_certification_launcher.Task9ExternalProviderBlockerStore", return_value=store), \
         patch("services.certification.task9_live_paper_certification_launcher.Task9SingleProcessLock", return_value=lock), \
         patch.object(launcher, "_startup_safety"), \
         patch("services.certification.task9_live_paper_certification_launcher.load_or_create_task9_run_manifest", return_value=manifest), \
         patch.object(launcher, "_run_one_cycle", side_effect=lambda _manifest, **kwargs: selected.append(kwargs["precomposed_timeframe_provider_factory"])):
        launcher.run(max_cycles=1)

    assert len(selected) == 1 and callable(selected[0])
    assert active["status"] == "ACTIVE"
    store.load.assert_called_once_with("task925-run")


def test_non_rate_limit_active_blocker_remains_rejected_without_fallback(tmp_path):
    _write_valid_startup_preflight(tmp_path)

    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path, official_run_id="task925-run",
            startup_preflight_id="task9102-preflight",
            runtime_config_snapshot_id="task9-runtime-config-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            runtime_config_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            campaign_id="task9102-campaign",
            market_date=AS_OF.date(),
        task9_evidence_dependencies_factory=lambda **_: None,
        runtime_factory=lambda **_: None, clock=lambda: AS_OF,
        sleep=lambda _: None,
        session_state_resolver=_session_resolver,
    )
    blocker = {
        "status": "ACTIVE", "provider": "ANGEL_ONE", "endpoint": "historical-data",
        "last_failure_reason": "HISTORICAL-DATA_UNAVAILABLE",
        "next_probe_not_before": (AS_OF + timedelta(hours=1)).isoformat(),
        "blocker_code": "EXTERNAL_PROVIDER_CLIENT_CODE_QUOTA_STATE",
    }
    with patch("services.certification.task9_live_paper_certification_launcher.Task9ExternalProviderBlockerStore", return_value=SimpleNamespace(load=lambda _: blocker)), \
         patch.object(launcher, "_startup_safety") as safety, \
         patch.object(launcher, "_run_one_cycle") as run_cycle:
        with pytest.raises(Task9ExternalProviderBlockedError, match="TASK9_EXTERNAL_PROVIDER_BLOCKER_ACTIVE"):
            launcher.run(max_cycles=1)

    safety.assert_not_called()
    run_cycle.assert_not_called()
