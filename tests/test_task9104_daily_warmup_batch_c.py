from datetime import datetime, time, timedelta
import inspect
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.certification.task9_parent_evidence_composition import (
    build_task9_parent_evidence_dependencies,
)
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)
from services.historical_data_cache import HistoricalDataCache
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    required_closed_candle_at,
    task9_required_completed_daily_candle_at,
)
from services.market.task9_historical_websocket_composition import (
    build_task9_precomposed_timeframe_provider,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_live_provider_readers import (
    market_spec_for,
)
from services.task9_daily_historical_warmup_retry import (
    Task9DailyWarmupRetryStore,
)


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 8, 11, 13, 15, tzinfo=IST)
TIMEFRAME_MINUTES = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
}


def _response_ending_at(required, *, count, step):
    return {
        "status": True,
        "data": [
            [
                (
                    required
                    - step * (count - index - 1)
                ).isoformat(),
                24500.0 + index * 5.0,
                24506.0 + index * 5.0,
                24496.0 + index * 5.0,
                24505.0 + index * 5.0,
                1000 + index,
            ]
            for index in range(count)
        ],
    }


def _daily_response(required, *, count=50):
    return _response_ending_at(
        required,
        count=count,
        step=timedelta(days=1),
    )


class _DailyClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_historical_data(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _session_resolver(*, market, evaluated_at, market_date):
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
        policy_id="task9104-batch-c-session",
        policy_version="1",
    )


def _seed_intraday_cache(cache):
    for timeframe, minutes in TIMEFRAME_MINUTES.items():
        # Task 9 hourly candles are anchored to the 09:15 session open.
        # At the fixed 13:15 test boundary, 12:15 is the latest completed
        # hourly candle. Other intraday frames use the shared boundary
        # helper directly.
        required = (
            NOW - timedelta(hours=1)
            if timeframe == "1h"
            else required_closed_candle_at(
                timeframe,
                NOW,
                exchange="NSE",
            )
        )
        cache.set(
            "NSE",
            "99926000",
            timeframe,
            _response_ending_at(
                required,
                count=60,
                step=timedelta(minutes=minutes),
            ),
            requested_until=NOW.isoformat(),
        )


def _build_service(tmp_path, client, cache):
    return LiveMultiTimeframeData(
        client=client,
        cache=cache,
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=(
            Task9DailyWarmupRetryStore(
                tmp_path / "retry.json",
                time_function=lambda: 100.0,
            )
        ),
    )


def _capture_from_cache_only_provider(tmp_path, cache):
    factory = build_task9_precomposed_timeframe_provider(
        live_stream_root=tmp_path / "live-stream",
        session_state_resolver=_session_resolver,
    )
    provider = factory(
        type("DataService", (), {"cache": cache})()
    )
    precomposed = provider(
        exchange="NSE",
        symboltoken="99926000",
        end_time=NOW,
    )
    spec = market_spec_for("NIFTY", "NSE")
    capture = CertifiedLiveCapturedEvidenceV1(
        underlying_symbol=spec.underlying_symbol,
        spot_exchange=spec.exchange,
        spot_token=spec.symboltoken,
        option_exchange=spec.option_exchange,
        spot_payload={"spot_price": 25000.0},
        candle_rows_by_timeframe={
            timeframe: tuple(rows)
            for timeframe, rows
            in precomposed["rows_by_timeframe"].items()
        },
        option_contracts=(),
        provider_timestamp=NOW,
        evaluated_at=NOW,
        provider_blockers=("OPTION_CHAIN_UNAVAILABLE",),
        cache_metadata=precomposed["cache_metadata"],
    )
    return precomposed, capture


def _evaluate(capture, *, suffix):
    session = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=NOW,
        evaluated_at=NOW,
        validation_mode="LENIENT_ANALYSIS",
        id_factory=lambda: f"session:{suffix}",
    )
    return evaluate_captured_certified_market_candidate(
        captured_evidence=capture,
        session_validation=session,
        policy_source=LiveCandidatePolicySourceV1.unavailable(),
        parent_cycle_id=f"parent:{suffix}",
        candidate_id=f"candidate:{suffix}",
        observation_id=f"observation:{suffix}",
        engines=build_default_live_canonical_evidence_engines(),
    )


def test_c_successful_warmup_reaches_real_ready_technical_path(tmp_path):
    cache = HistoricalDataCache(
        tmp_path / "cache.json",
        time_function=lambda: 100.0,
    )
    _seed_intraday_cache(cache)
    required = task9_required_completed_daily_candle_at(
        NOW,
        exchange="NSE",
    )
    client = _DailyClient(_daily_response(required))
    service = _build_service(tmp_path, client, cache)

    warmup = service.ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=NOW,
    )
    precomposed, capture = _capture_from_cache_only_provider(
        tmp_path,
        cache,
    )
    evaluation = _evaluate(capture, suffix="with-1d")
    technical = evaluation.evidence.technical

    assert warmup["refresh_outcome"] == "REFRESHED"
    assert warmup["provider_call_count"] == 1
    assert len(client.calls) == 1
    assert precomposed["cache_metadata"]["1d"]["captured"] is True
    assert "1d" in precomposed["rows_by_timeframe"]
    assert len(precomposed["rows_by_timeframe"]["1d"]) == 50
    assert technical.status == "READY"
    assert technical.unavailable_timeframes == ()
    assert not any(
        "TIMEFRAME_UNAVAILABLE_1D" in warning.upper()
        for warning in technical.warnings
    )
    assert evaluation.candidate.eligibility != "ELIGIBLE"
    assert "OPTION_CHAIN_UNAVAILABLE" in evaluation.candidate.blockers


def test_c_failed_optional_warmup_preserves_mandatory_technical_path(
    tmp_path,
):
    cache = HistoricalDataCache(
        tmp_path / "cache.json",
        time_function=lambda: 100.0,
    )
    _seed_intraday_cache(cache)
    client = _DailyClient(TimeoutError("optional daily timeout"))
    service = _build_service(tmp_path, client, cache)

    warmup = service.ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=NOW,
    )
    calls_after_warmup = len(client.calls)
    precomposed, capture = _capture_from_cache_only_provider(
        tmp_path,
        cache,
    )
    evaluation = _evaluate(capture, suffix="without-1d")
    technical = evaluation.evidence.technical
    warnings = tuple(
        warning.upper()
        for warning in technical.warnings
    )

    assert warmup["refresh_outcome"] == "UNAVAILABLE"
    assert warmup["warnings"] == (
        "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
    )
    assert calls_after_warmup == 1
    assert len(client.calls) == calls_after_warmup
    assert precomposed["cache_metadata"]["1d"]["captured"] is False
    assert "1d" not in precomposed["rows_by_timeframe"]
    assert "5m" in precomposed["rows_by_timeframe"]
    assert technical.status == "READY_WITH_WARNINGS"
    assert technical.unavailable_timeframes == ("1d",)
    assert warnings == (
        "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
        "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",
    )
    assert "TECHNICAL_TIMEFRAME_UNAVAILABLE_5M" not in warnings
    assert technical.blockers == ()


def test_c_parent_warmup_owner_precedes_child_cycle_construction():
    source = inspect.getsource(
        build_task9_parent_evidence_dependencies
    )

    warmup_index = source.index("warmup = ensure_daily(")
    cycle_index = source.index("requested = datetime.now(timezone.utc)")

    assert warmup_index < cycle_index
    assert source.count("warmup = ensure_daily(") == 1
    assert "for symbol, exchange in _SUPPORTED_MARKETS:" in source
    assert "spec.symboltoken" in source[warmup_index - 500:warmup_index + 500]


def test_c_collector_offline_and_dashboard_have_no_daily_warmup_owner():
    prohibited = (
        "ensure_daily_cache_coverage(",
        "get_historical_data(",
    )
    paths = (
        Path("services/certification/task9_live_websocket_collector.py"),
        Path("services/market/task9_live_tick_stream.py"),
        Path("services/certification/task9_offline_replay_evidence_builder.py"),
        Path("dashboard/dashboard_v2.py"),
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in prohibited:
            assert token not in source, f"{path} unexpectedly contains {token}"


