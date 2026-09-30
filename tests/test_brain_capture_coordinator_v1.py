from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from services.brain.capture_coordinator_v1 import (
    CAPTURE_COORDINATOR_RESULT_SCHEMA_V1,
    CaptureResultV1,
    IndexCaptureSourcesV1,
    McxCaptureSourcesV1,
    capture_index_sources_v1,
    capture_mcx_sources_v1,
)
from services.brain.snapshot_journal_v1 import (
    SnapshotJournalConflictError,
    enumerate_snapshot_journal_v1,
    replay_snapshot_journal_v1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxEventRiskSourceV1,
    McxNativeSourceV1,
)


NOW = datetime(
    2026,
    9,
    30,
    11,
    30,
    tzinfo=timezone.utc,
)

SESSION_ID = "2026-09-30"

INDEX_STRATEGY = "NS_DESIGN_B_BID_AUTH_V4"
INDEX_EPOCH = "NS_CERT_20260929_V4"

MCX_IDENTITIES = {
    "CRUDEOILM": (
        "MCX_POST_PRECISION_V5",
        "POST_PRECISION_V5",
    ),
    "GOLDM": (
        "MCX_GOLDM_PRECERT_V3",
        "GOLDM_PRECERT_V3",
    ),
    "NATGASMINI": (
        "MCX_NATGASMINI_PRECERT_V2",
        "NATGASMINI_PRECERT_V2",
    ),
}


def _full_index_sources(
    market: str,
    *,
    timestamp: datetime = NOW,
    pcr: float = 0.30,
) -> IndexCaptureSourcesV1:
    return IndexCaptureSourcesV1(
        premarket=IndexPremarketSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            previous_session_date="2026-09-29",
            previous_close=22716.20,
            global_bias="BULLISH",
            vix_value=12.4,
            combined_net=-3027.51,
            flow_direction="BEARISH",
            event_status="UNVERIFIED",
            event_freshness="UNKNOWN",
            event_source_authoritative=False,
            event_provider_block_entries=False,
            event_hard_block_eligible=False,
        ),
        news=IndexNewsSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            status="DEGRADED",
            freshness="FRESH",
            source="LEGACY_NEWS_ENGINE",
            sentiment="BULLISH",
            direction="BULLISH",
            bullish_count=5,
            bearish_count=1,
            headline_count=20,
            feeds_available=2,
            feeds_expected=3,
        ),
        technical=IndexTechnicalSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            mtf_direction="BULLISH",
            rsi=57.0,
            rsi_direction="BULLISH",
            adx=25.0,
            regime="TRENDING",
        ),
        breadth=IndexBreadthSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            breadth_score=0.30,
            breadth_direction="BULLISH",
        ),
        option_chain=IndexOptionChainSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            pcr_value=pcr,
            pcr_direction="BULLISH",
            pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
            max_pain=22700.0,
        ),
    )


def _partial_index_sources(
    market: str,
    *,
    timestamp: datetime = NOW,
) -> IndexCaptureSourcesV1:
    return IndexCaptureSourcesV1(
        news=IndexNewsSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            status="DEGRADED",
            freshness="FRESH",
            source="LEGACY_NEWS_ENGINE",
            sentiment="NEUTRAL",
            direction="NEUTRAL",
            bullish_count=1,
            bearish_count=1,
            headline_count=2,
            feeds_available=2,
            feeds_expected=3,
        ),
    )


def _full_mcx_sources(
    market: str,
    *,
    timestamp: datetime = NOW,
    stable_pcr: float = 0.94,
    pcr_direction: str = "BULLISH",
    pcr_interpretation: str = "MCX_NATIVE_SOURCE_RULE",
) -> McxCaptureSourcesV1:
    return McxCaptureSourcesV1(
        native=McxNativeSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            mtf_direction="BULLISH",
            regime="TREND",
            structure="ABOVE_VWAP",
            future_ltp=6200.0,
            price_oi_state="LONG_BUILDUP",
            raw_pcr=stable_pcr,
            stable_pcr=stable_pcr,
            max_pain=6200.0,
            pcr_direction=pcr_direction,
            pcr_interpretation=pcr_interpretation,
        ),
        event_risk=McxEventRiskSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            status="UNVERIFIED",
            freshness="UNKNOWN",
            event_state="NO_VERIFIED_BLOCK",
            source_authoritative=False,
            provider_block_entries=False,
            hard_block_eligible=False,
        ),
    )


def _partial_mcx_sources(
    market: str,
    *,
    timestamp: datetime = NOW,
) -> McxCaptureSourcesV1:
    return McxCaptureSourcesV1(
        native=McxNativeSourceV1(
            market=market,
            observed_at=timestamp,
            generated_at=timestamp,
            mtf_direction="MIXED",
            regime="RANGE",
            structure="AT_VWAP",
            future_ltp=6200.0,
            price_oi_state="NEUTRAL",
            raw_pcr=0.90,
            stable_pcr=0.90,
            max_pain=6200.0,
            pcr_direction="NEUTRAL",
            pcr_interpretation="MCX_NATIVE_SOURCE_RULE",
        )
    )


def _capture_index(
    root: Path,
    market: str,
    *,
    timestamp: datetime = NOW,
    pcr: float = 0.30,
    sources: IndexCaptureSourcesV1 | None = None,
) -> CaptureResultV1:
    if sources is None:
        sources = _full_index_sources(
            market,
            timestamp=timestamp,
            pcr=pcr,
        )

    return capture_index_sources_v1(
        journal_root=root,
        session_id=SESSION_ID,
        market=market,
        snapshot_at=timestamp,
        generated_at=timestamp,
        sources=sources,
        source_strategy_version=INDEX_STRATEGY,
        source_policy_epoch=INDEX_EPOCH,
        source_runtime_ref="R2.2",
    )


def _capture_mcx(
    root: Path,
    market: str,
    *,
    timestamp: datetime = NOW,
    sources: McxCaptureSourcesV1 | None = None,
) -> CaptureResultV1:
    strategy, epoch = MCX_IDENTITIES[market]

    if sources is None:
        sources = _full_mcx_sources(
            market,
            timestamp=timestamp,
        )

    return capture_mcx_sources_v1(
        journal_root=root,
        session_id=SESSION_ID,
        market=market,
        snapshot_at=timestamp,
        generated_at=timestamp,
        sources=sources,
        source_strategy_version=strategy,
        source_policy_epoch=epoch,
        source_runtime_ref="R2.2",
    )


@pytest.mark.parametrize(
    "market",
    (
        "NIFTY",
        "SENSEX",
    ),
)
def test_full_index_capture_is_complete_and_replayable(
    tmp_path,
    market,
):
    result = _capture_index(
        tmp_path,
        market,
    )

    assert result.production_complete is True
    assert result.production_coverage_pct == 100.0
    assert len(result.expected_production_analyzers) == 11
    assert len(result.present_production_analyzers) == 11
    assert result.missing_production_analyzers == ()

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market=market,
        session_id=SESSION_ID,
    )

    assert len(replayed) == 1
    assert replayed[0].snapshot_sha256 == result.snapshot_sha256


@pytest.mark.parametrize(
    "market",
    (
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    ),
)
def test_full_mcx_capture_is_complete_and_replayable(
    tmp_path,
    market,
):
    result = _capture_mcx(
        tmp_path,
        market,
    )

    assert result.production_complete is True
    assert result.production_coverage_pct == 100.0
    assert len(result.expected_production_analyzers) == 6
    assert len(result.present_production_analyzers) == 6
    assert result.missing_production_analyzers == ()

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market=market,
        session_id=SESSION_ID,
    )

    assert len(replayed) == 1
    assert replayed[0].snapshot_sha256 == result.snapshot_sha256


def test_partial_index_capture_preserves_missing_coverage(
    tmp_path,
):
    result = _capture_index(
        tmp_path,
        "NIFTY",
        sources=_partial_index_sources("NIFTY"),
    )

    assert result.production_complete is False
    assert len(result.expected_production_analyzers) == 11
    assert result.present_production_analyzers == (
        "index.news.legacy_v1",
    )
    assert "index.news.legacy_v1" not in result.missing_production_analyzers
    assert len(result.missing_production_analyzers) == 10


def test_partial_mcx_capture_preserves_missing_event_risk(
    tmp_path,
):
    result = _capture_mcx(
        tmp_path,
        "CRUDEOILM",
        sources=_partial_mcx_sources("CRUDEOILM"),
    )

    assert result.production_complete is False
    assert len(result.expected_production_analyzers) == 6
    assert len(result.present_production_analyzers) == 5
    assert result.missing_production_analyzers == (
        "mcx.event_risk.native_v1",
    )


def test_identical_capture_is_idempotent_at_coordinator_boundary(
    tmp_path,
):
    sources = _full_index_sources("NIFTY")

    first = _capture_index(
        tmp_path,
        "NIFTY",
        sources=sources,
    )

    second = _capture_index(
        tmp_path,
        "NIFTY",
        sources=sources,
    )

    assert first == second

    entries = enumerate_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id=SESSION_ID,
    )

    assert len(entries) == 1


def test_same_slot_different_snapshot_is_rejected(
    tmp_path,
):
    first = _capture_index(
        tmp_path,
        "NIFTY",
        pcr=0.30,
    )

    with pytest.raises(
        SnapshotJournalConflictError,
    ):
        _capture_index(
            tmp_path,
            "NIFTY",
            pcr=0.31,
        )

    entries = enumerate_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id=SESSION_ID,
    )

    assert len(entries) == 1
    assert entries[0].snapshot_sha256 == first.snapshot_sha256


def test_replay_preserves_strategy_policy_and_runtime_identity(
    tmp_path,
):
    result = _capture_mcx(
        tmp_path,
        "GOLDM",
    )

    replayed = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="GOLDM",
        session_id=SESSION_ID,
    )[0]

    assert replayed.snapshot_sha256 == result.snapshot_sha256
    assert replayed.source_strategy_version == "MCX_GOLDM_PRECERT_V3"
    assert replayed.source_policy_epoch == "GOLDM_PRECERT_V3"
    assert replayed.source_runtime_ref == "R2.2"


def test_index_and_mcx_pcr_source_semantics_are_not_normalized(
    tmp_path,
):
    _capture_index(
        tmp_path,
        "NIFTY",
        pcr=0.30,
    )

    mcx_sources = _full_mcx_sources(
        "CRUDEOILM",
        stable_pcr=0.30,
        pcr_direction="BEARISH",
        pcr_interpretation="MCX_NATIVE_LOW_PCR_BEARISH",
    )

    _capture_mcx(
        tmp_path,
        "CRUDEOILM",
        sources=mcx_sources,
    )

    index_snapshot = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id=SESSION_ID,
    )[0]

    mcx_snapshot = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="CRUDEOILM",
        session_id=SESSION_ID,
    )[0]

    index_result = next(
        result
        for result in index_snapshot.analyzer_results
        if result.analyzer == "index.option_chain.legacy_v1"
    )

    mcx_result = next(
        result
        for result in mcx_snapshot.analyzer_results
        if result.analyzer == "mcx.pcr.native_v1"
    )

    index_pcr = next(
        evidence
        for evidence in index_result.evidence
        if evidence.feature == "PCR"
    )

    mcx_pcr = next(
        evidence
        for evidence in mcx_result.evidence
        if evidence.feature == "STABLE_PCR"
    )

    assert index_pcr.value == 0.30
    assert index_pcr.direction == "BULLISH"
    assert dict(index_pcr.metadata)["source_interpretation"] == (
        "INDEX_LEGACY_SOURCE_RULE"
    )

    assert mcx_pcr.value == 0.30
    assert mcx_pcr.direction == "BEARISH"
    assert dict(mcx_pcr.metadata)["source_interpretation"] == (
        "MCX_NATIVE_LOW_PCR_BEARISH"
    )


def test_unverified_event_evidence_remains_unverified(
    tmp_path,
):
    _capture_index(
        tmp_path,
        "NIFTY",
    )

    _capture_mcx(
        tmp_path,
        "CRUDEOILM",
    )

    index_snapshot = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="NIFTY",
        session_id=SESSION_ID,
    )[0]

    mcx_snapshot = replay_snapshot_journal_v1(
        journal_root=tmp_path,
        market="CRUDEOILM",
        session_id=SESSION_ID,
    )[0]

    index_event = next(
        result
        for result in index_snapshot.analyzer_results
        if result.analyzer == "index.event_calendar.legacy_v1"
    )

    mcx_event = next(
        result
        for result in mcx_snapshot.analyzer_results
        if result.analyzer == "mcx.event_risk.native_v1"
    )

    assert any(
        evidence.status == "UNVERIFIED"
        and evidence.source_authoritative is False
        for evidence in index_event.evidence
    )

    assert any(
        evidence.status == "UNVERIFIED"
        and evidence.source_authoritative is False
        for evidence in mcx_event.evidence
    )


def test_source_market_mismatch_is_rejected_before_capture(
    tmp_path,
):
    sources = _full_index_sources("SENSEX")

    with pytest.raises(
        ValueError,
        match="must equal capture market",
    ):
        _capture_index(
            tmp_path,
            "NIFTY",
            sources=sources,
        )

    assert not (
        tmp_path
        / "NIFTY"
    ).exists()


def test_wrong_market_family_is_rejected(
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="index capture market",
    ):
        capture_index_sources_v1(
            journal_root=tmp_path,
            session_id=SESSION_ID,
            market="CRUDEOILM",
            snapshot_at=NOW,
            generated_at=NOW,
            sources=_full_index_sources("NIFTY"),
            source_strategy_version=INDEX_STRATEGY,
            source_policy_epoch=INDEX_EPOCH,
            source_runtime_ref="R2.2",
        )

    with pytest.raises(
        ValueError,
        match="MCX capture market",
    ):
        capture_mcx_sources_v1(
            journal_root=tmp_path,
            session_id=SESSION_ID,
            market="NIFTY",
            snapshot_at=NOW,
            generated_at=NOW,
            sources=_full_mcx_sources("CRUDEOILM"),
            source_strategy_version="MCX_POST_PRECISION_V5",
            source_policy_epoch="POST_PRECISION_V5",
            source_runtime_ref="R2.2",
        )


def test_naive_capture_timestamps_are_rejected(
    tmp_path,
):
    naive = NOW.replace(
        tzinfo=None
    )

    with pytest.raises(
        ValueError,
        match="snapshot_at must be timezone-aware",
    ):
        capture_index_sources_v1(
            journal_root=tmp_path,
            session_id=SESSION_ID,
            market="NIFTY",
            snapshot_at=naive,
            generated_at=NOW,
            sources=_full_index_sources("NIFTY"),
            source_strategy_version=INDEX_STRATEGY,
            source_policy_epoch=INDEX_EPOCH,
            source_runtime_ref="R2.2",
        )

    with pytest.raises(
        ValueError,
        match="generated_at must be timezone-aware",
    ):
        capture_index_sources_v1(
            journal_root=tmp_path,
            session_id=SESSION_ID,
            market="NIFTY",
            snapshot_at=NOW,
            generated_at=naive,
            sources=_full_index_sources("NIFTY"),
            source_strategy_version=INDEX_STRATEGY,
            source_policy_epoch=INDEX_EPOCH,
            source_runtime_ref="R2.2",
        )


def test_empty_source_bundles_are_rejected():
    with pytest.raises(
        ValueError,
        match="at least one source",
    ):
        IndexCaptureSourcesV1()

    with pytest.raises(
        ValueError,
        match="at least one source",
    ):
        McxCaptureSourcesV1()


def test_capture_result_is_permanently_zero_authority(
    tmp_path,
):
    result = _capture_index(
        tmp_path,
        "NIFTY",
    )

    assert result.execution_authority is False
    assert result.decision_authority is False
    assert result.risk_authority is False
    assert result.position_authority is False
    assert result.certification_authority is False

    with pytest.raises(
        ValueError,
        match="execution_authority is permanently False",
    ):
        replace(
            result,
            execution_authority=True,
        )

    with pytest.raises(
        ValueError,
        match="unsupported capture result schema",
    ):
        replace(
            result,
            schema_version="BRAIN_CAPTURE_COORDINATOR_RESULT_V2",
        )


def test_capture_result_to_dict_is_json_serializable(
    tmp_path,
):
    result = _capture_index(
        tmp_path,
        "NIFTY",
    )

    payload = result.to_dict()

    encoded = json.dumps(
        payload,
        sort_keys=True,
    )

    assert payload["schema_version"] == (
        CAPTURE_COORDINATOR_RESULT_SCHEMA_V1
    )
    assert payload["snapshot_sha256"] == result.snapshot_sha256
    assert payload["execution_authority"] is False
    assert isinstance(encoded, str)


def test_capture_coordinator_has_no_provider_or_broker_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "capture_coordinator_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name.lower()
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imports.append(
                (
                    node.module
                    or ""
                ).lower()
            )

    forbidden = (
        "fyers",
        "smartapi",
        "requests",
        "yfinance",
        "broker",
        "execution",
    )

    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )
