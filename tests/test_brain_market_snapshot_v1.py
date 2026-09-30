from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
    build_market_snapshot_v1,
)
from services.brain.source_adapters_v1 import (
    IndexBreadthSourceV1,
    IndexNewsSourceV1,
    IndexOptionChainSourceV1,
    IndexPremarketSourceV1,
    IndexTechnicalSourceV1,
    McxEventRiskSourceV1,
    McxNativeSourceV1,
    adapt_index_breadth_v1,
    adapt_index_news_v1,
    adapt_index_option_chain_v1,
    adapt_index_premarket_v1,
    adapt_index_technical_v1,
    adapt_mcx_event_risk_v1,
    adapt_mcx_native_v1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)


NOW = datetime(
    2026,
    9,
    30,
    8,
    30,
    tzinfo=timezone.utc,
)


def full_index_results(
    market="NIFTY",
):
    return (
        *adapt_index_premarket_v1(
            IndexPremarketSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                previous_session_date="2026-09-29",
                previous_open=22732.45,
                previous_high=22753.25,
                previous_low=22569.65,
                previous_close=22716.20,
                gap_pct=0.10,
                gap_direction="BULLISH",
                global_bias="BULLISH",
                global_score=0.60,
                vix_value=12.4,
                combined_net=-3027.51,
                flow_direction="BEARISH",
                event_status="UNVERIFIED",
                event_source_authoritative=False,
            )
        ),

        adapt_index_news_v1(
            IndexNewsSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
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
            )
        ),

        *adapt_index_technical_v1(
            IndexTechnicalSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                mtf_direction="BULLISH",
                rsi=57.0,
                rsi_direction="BULLISH",
                adx=25.0,
                adx_direction="BULLISH",
                ema_state="EMA20_ABOVE_EMA50",
                ema_direction="BULLISH",
                macd_state="POSITIVE",
                macd_direction="BULLISH",
                bollinger_state="MID_TO_UPPER",
                bollinger_direction="BULLISH",
                regime="TRENDING",
                regime_direction="BULLISH",
            )
        ),

        adapt_index_breadth_v1(
            IndexBreadthSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                breadth_score=0.30,
                breadth_direction="BULLISH",
                advances=32,
                declines=17,
                unchanged=1,
                heavyweight_direction="MIXED",
            )
        ),

        adapt_index_option_chain_v1(
            IndexOptionChainSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                pcr_value=0.30,
                pcr_direction="BULLISH",
                pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
                max_pain=22700.0,
                support=22600.0,
                resistance=22800.0,
                atm_strike=22700.0,
                expiry="2026-10-01",
                chain_coverage_pct=100.0,
            )
        ),
    )


def full_mcx_results(
    market="CRUDEOILM",
):
    return (
        *adapt_mcx_native_v1(
            McxNativeSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                mtf_direction="BULLISH",
                regime="TREND",
                regime_direction="BULLISH",
                structure="ABOVE_VWAP",
                structure_direction="BULLISH",
                vwap_relation="ABOVE",
                future_ltp=6200.0,
                price_change_pct=0.4,
                oi_change_pct=1.2,
                price_oi_state="LONG_BUILDUP",
                price_oi_direction="BULLISH",
                raw_pcr=0.90,
                stable_pcr=0.94,
                max_pain=6200.0,
                pcr_direction="BULLISH",
                pcr_interpretation="MCX_NATIVE_SOURCE_RULE",
            )
        ),

        adapt_mcx_event_risk_v1(
            McxEventRiskSourceV1(
                market=market,
                observed_at=NOW,
                generated_at=NOW,
                status="UNVERIFIED",
                freshness="UNKNOWN",
                event_state="NO_VERIFIED_BLOCK",
                source_authoritative=False,
                provider_block_entries=False,
                hard_block_eligible=False,
            )
        ),
    )


def build_index_snapshot(
    results=None,
):
    if results is None:
        results = full_index_results()

    return build_market_snapshot_v1(
        market="NIFTY",
        snapshot_at=NOW,
        generated_at=NOW,
        analyzer_results=results,
        source_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        source_policy_epoch="NS_CERT_20260929_V4",
        source_runtime_ref="R2.2",
    )


def test_full_nifty_snapshot_is_eleven_of_eleven_complete():
    snapshot = build_index_snapshot()

    assert len(
        snapshot.expected_production_analyzers
    ) == 11

    assert len(
        snapshot.production_analyzer_ids_present
    ) == 11

    assert snapshot.production_coverage_pct == 100.0
    assert snapshot.production_complete is True
    assert snapshot.missing_production_analyzers == ()


def test_full_mcx_snapshot_is_six_of_six_complete():
    snapshot = build_market_snapshot_v1(
        market="CRUDEOILM",
        snapshot_at=NOW,
        generated_at=NOW,
        analyzer_results=full_mcx_results(),
        source_strategy_version="MCX_POST_PRECISION_V5",
        source_policy_epoch="POST_PRECISION_V5",
        source_runtime_ref="R2.2",
    )

    assert len(
        snapshot.expected_production_analyzers
    ) == 6

    assert len(
        snapshot.production_analyzer_ids_present
    ) == 6

    assert snapshot.production_coverage_pct == 100.0
    assert snapshot.production_complete is True


def test_partial_snapshot_reports_exact_missing_analyzers():
    results = full_index_results()

    removed = {
        "index.news.legacy_v1",
        "index.breadth.legacy_v1",
    }

    partial = tuple(
        result
        for result in results
        if result.analyzer not in removed
    )

    snapshot = build_index_snapshot(
        partial
    )

    assert snapshot.production_complete is False

    assert set(
        snapshot.missing_production_analyzers
    ) == removed

    assert snapshot.production_coverage_pct == pytest.approx(
        100.0
        * 9
        / 11
    )


def test_hash_is_identical_when_analyzer_order_changes():
    results = full_index_results()

    first = build_index_snapshot(
        results
    )

    second = build_index_snapshot(
        tuple(
            reversed(
                results
            )
        )
    )

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.canonical_json() == second.canonical_json()


def test_hash_is_identical_when_evidence_order_changes_inside_result():
    results = list(
        full_index_results()
    )

    position = next(
        index
        for index, result
        in enumerate(
            results
        )
        if result.analyzer
        == "index.option_chain.legacy_v1"
    )

    original = results[
        position
    ]

    reordered = AnalyzerResultV1(
        result_id=original.result_id,
        market=original.market,
        analyzer=original.analyzer,
        analyzer_version=original.analyzer_version,
        generated_at=original.generated_at,
        status=original.status,
        evidence=tuple(
            reversed(
                original.evidence
            )
        ),
        blockers=tuple(
            reversed(
                original.blockers
            )
        ),
        warnings=tuple(
            reversed(
                original.warnings
            )
        ),
        execution_authority=False,
    )

    results[
        position
    ] = reordered

    first = build_index_snapshot()
    second = build_index_snapshot(
        tuple(
            results
        )
    )

    assert first.snapshot_sha256 == second.snapshot_sha256


def test_evidence_change_changes_snapshot_hash():
    first = build_index_snapshot()

    changed = list(
        full_index_results()
    )

    option_index = next(
        index
        for index, result
        in enumerate(
            changed
        )
        if result.analyzer
        == "index.option_chain.legacy_v1"
    )

    changed[
        option_index
    ] = adapt_index_option_chain_v1(
        IndexOptionChainSourceV1(
            market="NIFTY",
            observed_at=NOW,
            generated_at=NOW,
            pcr_value=0.31,
            pcr_direction="BULLISH",
            pcr_interpretation="INDEX_LEGACY_SOURCE_RULE",
            max_pain=22700.0,
            support=22600.0,
            resistance=22800.0,
            atm_strike=22700.0,
            expiry="2026-10-01",
            chain_coverage_pct=100.0,
        )
    )

    second = build_index_snapshot(
        tuple(
            changed
        )
    )

    assert first.snapshot_sha256 != second.snapshot_sha256


def test_snapshot_hash_is_lowercase_sha256_hex():
    value = build_index_snapshot().snapshot_sha256

    assert len(value) == 64
    assert value == value.lower()

    int(
        value,
        16,
    )


def test_snapshot_to_dict_is_json_serializable():
    payload = build_index_snapshot().to_dict()

    json.dumps(
        payload,
        sort_keys=True,
    )

    assert payload[
        "schema_version"
    ] == "BRAIN_MARKET_SNAPSHOT_V1"

    assert payload[
        "snapshot_sha256"
    ]


def test_snapshot_preserves_source_policy_identity():
    snapshot = build_index_snapshot()

    assert (
        snapshot.source_strategy_version
        == "NS_DESIGN_B_BID_AUTH_V4"
    )

    assert (
        snapshot.source_policy_epoch
        == "NS_CERT_20260929_V4"
    )

    assert snapshot.source_runtime_ref == "R2.2"


def test_snapshot_records_unverified_evidence_count():
    snapshot = build_index_snapshot()

    counts = snapshot.evidence_status_counts()

    assert counts[
        "UNVERIFIED"
    ] >= 1


def test_snapshot_records_unknown_freshness():
    snapshot = build_index_snapshot()

    counts = snapshot.freshness_counts()

    assert counts[
        "UNKNOWN"
    ] >= 1


def test_snapshot_requires_timezone_aware_snapshot_time():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_market_snapshot_v1(
            market="NIFTY",
            snapshot_at=datetime(
                2026,
                9,
                30,
                12,
                0,
            ),
            generated_at=NOW,
            analyzer_results=full_index_results(),
        )


def test_snapshot_rejects_duplicate_analyzer_results():
    result = full_index_results()[0]

    with pytest.raises(
        ValueError,
        match="duplicate analyzer result",
    ):
        build_market_snapshot_v1(
            market="NIFTY",
            snapshot_at=NOW,
            generated_at=NOW,
            analyzer_results=(
                result,
                result,
            ),
        )


def test_snapshot_rejects_result_from_other_market():
    sensex_result = full_index_results(
        "SENSEX"
    )[0]

    with pytest.raises(
        ValueError,
        match="market",
    ):
        build_market_snapshot_v1(
            market="NIFTY",
            snapshot_at=NOW,
            generated_at=NOW,
            analyzer_results=(
                sensex_result,
            ),
        )


def test_snapshot_rejects_unregistered_analyzer():
    evidence = EvidenceV1(
        evidence_id="UNKNOWN-1",
        market="NIFTY",
        analyzer="unknown.analyzer.v1",
        analyzer_version="1.0",
        category="TECHNICAL",
        feature="UNKNOWN",
        observed_at=NOW,
        generated_at=NOW,
        status="AVAILABLE",
        freshness="FRESH",
        source="TEST",
        value=1.0,
        direction="NEUTRAL",
    )

    result = AnalyzerResultV1(
        result_id="UNKNOWN-RESULT-1",
        market="NIFTY",
        analyzer="unknown.analyzer.v1",
        analyzer_version="1.0",
        generated_at=NOW,
        status="OK",
        evidence=(
            evidence,
        ),
    )

    with pytest.raises(
        ValueError,
        match="unregistered analyzer",
    ):
        build_market_snapshot_v1(
            market="NIFTY",
            snapshot_at=NOW,
            generated_at=NOW,
            analyzer_results=(
                result,
            ),
        )


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ],
)
def test_snapshot_authorities_are_permanently_false(
    field,
):
    base = build_index_snapshot()

    values = {
        "market":
            base.market,

        "snapshot_at":
            base.snapshot_at,

        "generated_at":
            base.generated_at,

        "analyzer_results":
            base.analyzer_results,

        "expected_production_analyzers":
            base.expected_production_analyzers,

        "registry_schema_version":
            base.registry_schema_version,

        field:
            True,
    }

    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        MarketSnapshotV1(
            **values
        )


def test_registered_shadow_result_does_not_count_as_production_coverage():
    evidence = EvidenceV1(
        evidence_id="SHADOW-1",
        market="NIFTY",
        analyzer="canonical.technical_intelligence.v1",
        analyzer_version="1.0",
        category="TECHNICAL",
        feature="SHADOW_TECHNICAL",
        observed_at=NOW,
        generated_at=NOW,
        status="AVAILABLE",
        freshness="FRESH",
        source="CANONICAL_TECHNICAL",
        value="BULLISH",
        direction="BULLISH",
    )

    shadow = AnalyzerResultV1(
        result_id="SHADOW-RESULT-1",
        market="NIFTY",
        analyzer="canonical.technical_intelligence.v1",
        analyzer_version="1.0",
        generated_at=NOW,
        status="OK",
        evidence=(
            evidence,
        ),
    )

    snapshot = build_index_snapshot(
        (
            *full_index_results(),
            shadow,
        )
    )

    assert snapshot.production_coverage_pct == 100.0
    assert snapshot.production_complete is True

    assert snapshot.extra_registered_analyzers == (
        "canonical.technical_intelligence.v1",
    )


def test_snapshot_generated_time_change_changes_hash():
    first = build_index_snapshot()

    second = build_market_snapshot_v1(
        market="NIFTY",
        snapshot_at=NOW,
        generated_at=NOW + timedelta(
            seconds=1
        ),
        analyzer_results=full_index_results(),
        source_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        source_policy_epoch="NS_CERT_20260929_V4",
        source_runtime_ref="R2.2",
    )

    assert first.snapshot_sha256 != second.snapshot_sha256