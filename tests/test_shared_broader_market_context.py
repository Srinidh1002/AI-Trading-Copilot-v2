from dataclasses import replace
from datetime import timedelta
from services.contracts.india_vix_capture_result_v1 import IndiaVixCaptureResultV1
from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1

import pytest

from services.analysis.shared_broader_market_context import CORRELATION_TIMEFRAME, build_certified_shared_broader_context
from services.market.angel_live_observation_normalizer import normalize_angel_live_observation
from services.paper_orchestration.certified_live_provider_readers import market_spec_for
from tests.test_task8_parent_typed_candidate_certification import NOW, _rows


def observation(symbol, exchange, spot, *, rows=None, evaluated_at=NOW):
    spec = market_spec_for(symbol, exchange)
    values = {name: _rows(name, spot) for name in ("5m", "15m", "1h", "1d")}
    if rows is not None:
        values = rows
    return normalize_angel_live_observation(
        spot_response={"data": {"ltp": spot, "tradingsymbol": symbol, "exchange": exchange, "symboltoken": spec.symboltoken}},
        candle_rows_by_timeframe=values, market_spec=spec, provider_timestamp=NOW, evaluated_at=evaluated_at,
    )


def test_shared_context_builds_nifty_and_sensex_primary_correlation_once_each():
    result = build_certified_shared_broader_context(
        nifty_observation=observation("NIFTY", "NSE", 25000.0),
        sensex_observation=observation("SENSEX", "BSE", 80000.0), evaluated_at=NOW,
    )
    assert CORRELATION_TIMEFRAME == "5m"
    assert result.nifty_broader_market.cross_market_evidence[0].related_symbol == "SENSEX"
    assert result.sensex_broader_market.cross_market_evidence[0].related_symbol == "NIFTY"
    assert "optional breadth evidence is unavailable" not in result.nifty_broader_market.warnings
    assert "optional volatility context is unavailable" not in result.sensex_broader_market.warnings
    assert "mandatory volatility context is unavailable" in result.sensex_broader_market.blockers
    assert result.shared_external_context is not None
    assert result.shared_external_context.cycle_id == result.cycle_id
    assert result.shared_external_context.evaluated_at == result.evaluated_at
    with pytest.raises(ValueError):
        replace(result, shared_external_context=replace(result.shared_external_context, cycle_id="wrong-cycle"))


def test_missing_timeframe_is_explicit_and_cross_market_boundary_is_fail_closed():
    rows = {name: _rows(name, 25000.0) for name in ("15m", "1h", "1d")}
    result = build_certified_shared_broader_context(
        nifty_observation=observation("NIFTY", "NSE", 25000.0, rows=rows),
        sensex_observation=observation("SENSEX", "BSE", 80000.0), evaluated_at=NOW,
    )
    assert result.blockers == ("CORRELATION_TIMEFRAME_UNAVAILABLE_5M",)
    assert result.nifty_broader_market is None
    with pytest.raises(ValueError):
        build_certified_shared_broader_context(
            nifty_observation=observation("NIFTY", "NSE", 25000.0),
            sensex_observation=observation("SENSEX", "BSE", 80000.0, evaluated_at=NOW + timedelta(seconds=1)),
            evaluated_at=NOW,
        )


def test_later_fresh_vix_uses_shared_post_capture_boundary_without_future_block():
    delayed = NOW + timedelta(seconds=130)
    capture = IndiaVixCaptureResultV1(
        capture_id="vix-capture", cycle_id="parent", canonical_name="INDIA_VIX", provider="ANGEL_SMARTAPI",
        provider_symbol="India VIX", provider_exchange="NSE", provider_token="99926017", instrument_type="AMXIDX",
        current_value=11.98, previous_close=11.76, provider_timestamp=delayed - timedelta(seconds=1), evaluated_at=delayed,
        provenance=MarketDataProvenanceV1("ANGEL_SMARTAPI", "India VIX", "NSE", "LIVE", delayed - timedelta(seconds=1), delayed, False, None, None), source_status="READY",
    )
    result = build_certified_shared_broader_context(
        nifty_observation=observation("NIFTY", "NSE", 25000.0, evaluated_at=delayed),
        sensex_observation=observation("SENSEX", "BSE", 80000.0, evaluated_at=delayed), evaluated_at=delayed, india_vix_capture=capture,
    )
    assert result.evaluated_at == delayed
    assert result.nifty_broader_market.volatility_context.volatility_regime == "LOW"
    assert "volatility source timestamp exceeds future tolerance" not in result.nifty_broader_market.blockers
    assert "optional breadth evidence is unavailable" not in result.nifty_broader_market.warnings


def _task9100_vix_capture(
    *,
    capture_id="task9100-vix",
    evaluated_at=NOW,
    provider_timestamp=None,
    current_value=12.0,
    previous_close=11.8,
    source_status="READY",
    blockers=(),
):
    if provider_timestamp is None:
        provider_timestamp = evaluated_at - timedelta(seconds=1)

    available = source_status == "READY"

    return IndiaVixCaptureResultV1(
        capture_id=capture_id,
        cycle_id=f"{capture_id}-parent",
        canonical_name="INDIA_VIX",
        provider="ANGEL_SMARTAPI",
        provider_symbol="India VIX" if available else None,
        provider_exchange="NSE" if available else None,
        provider_token="99926017" if available else None,
        instrument_type="AMXIDX" if available else None,
        current_value=current_value if available else None,
        previous_close=previous_close if available else None,
        provider_timestamp=provider_timestamp,
        evaluated_at=evaluated_at,
        provenance=MarketDataProvenanceV1(
            "ANGEL_SMARTAPI",
            "India VIX" if available else None,
            "NSE" if available else None,
            "LIVE",
            provider_timestamp,
            evaluated_at,
            False,
            None,
            None,
        ),
        source_status=source_status,
        blockers=blockers,
    )


def _task9100_shared_context(*, vix_capture, evaluated_at=NOW):
    return build_certified_shared_broader_context(
        nifty_observation=observation(
            "NIFTY",
            "NSE",
            25000.0,
            evaluated_at=evaluated_at,
        ),
        sensex_observation=observation(
            "SENSEX",
            "BSE",
            80000.0,
            evaluated_at=evaluated_at,
        ),
        evaluated_at=evaluated_at,
        india_vix_capture=vix_capture,
    )


@pytest.mark.parametrize(
    "market_attr",
    (
        "nifty_broader_market",
        "sensex_broader_market",
    ),
)
def test_task9100_missing_vix_blocks_task9_broader_context(
    market_attr,
):
    result = _task9100_shared_context(
        vix_capture=None,
    )

    broader = getattr(
        result,
        market_attr,
    )

    assert broader is not None

    assert broader.intelligence_status in {
        "BLOCKED",
        "UNAVAILABLE",
    }

    assert (
        "mandatory volatility context is unavailable"
        in broader.blockers
    )

    assert broader.volatility_context is None


@pytest.mark.parametrize(
    "market_attr",
    (
        "nifty_broader_market",
        "sensex_broader_market",
    ),
)
def test_task9100_unavailable_vix_blocks_task9_broader_context(
    market_attr,
):
    capture = _task9100_vix_capture(
        source_status="UNAVAILABLE",
        blockers=(
            "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH",
        ),
    )

    result = _task9100_shared_context(
        vix_capture=capture,
    )

    broader = getattr(
        result,
        market_attr,
    )

    assert broader is not None
    assert broader.volatility_context is not None

    assert broader.volatility_context.context_status in {
        "BLOCKED",
        "STALE",
        "UNAVAILABLE",
    }

    assert broader.intelligence_status in {
        "BLOCKED",
        "UNAVAILABLE",
    }

    assert (
        "mandatory volatility context is unavailable"
        in broader.blockers
    )


@pytest.mark.parametrize(
    "market_attr",
    (
        "nifty_broader_market",
        "sensex_broader_market",
    ),
)
def test_task9100_fresh_vix_satisfies_required_volatility_context(
    market_attr,
):
    capture = _task9100_vix_capture()

    result = _task9100_shared_context(
        vix_capture=capture,
    )

    broader = getattr(
        result,
        market_attr,
    )

    assert broader is not None
    assert broader.volatility_context is not None

    assert broader.volatility_context.context_status in {
        "READY",
        "READY_WITH_WARNINGS",
    }

    assert (
        "mandatory volatility context is unavailable"
        not in broader.blockers
    )


def test_task9100_vix_failure_does_not_poison_later_fresh_cycle():
    failed = _task9100_shared_context(
        vix_capture=None,
    )

    assert (
        "mandatory volatility context is unavailable"
        in failed.nifty_broader_market.blockers
    )
    assert (
        "mandatory volatility context is unavailable"
        in failed.sensex_broader_market.blockers
    )

    later = NOW + timedelta(seconds=60)

    recovered = _task9100_shared_context(
        vix_capture=_task9100_vix_capture(
            capture_id="task9100-vix-recovered",
            evaluated_at=later,
            provider_timestamp=(
                later - timedelta(seconds=1)
            ),
        ),
        evaluated_at=later,
    )

    for broader in (
        recovered.nifty_broader_market,
        recovered.sensex_broader_market,
    ):
        assert broader.volatility_context is not None

        assert broader.volatility_context.context_status in {
            "READY",
            "READY_WITH_WARNINGS",
        }

        assert (
            "mandatory volatility context is unavailable"
            not in broader.blockers
        )

def test_task9104_delayed_optional_vix_does_not_age_mandatory_cross_market():
    delayed = NOW + timedelta(seconds=310)

    capture = IndiaVixCaptureResultV1(
        capture_id="vix-delayed-cross-market-clock",
        cycle_id="parent",
        canonical_name="INDIA_VIX",
        provider="ANGEL_SMARTAPI",
        provider_symbol="India VIX",
        provider_exchange="NSE",
        provider_token="99926017",
        instrument_type="AMXIDX",
        current_value=11.98,
        previous_close=11.76,
        provider_timestamp=delayed - timedelta(seconds=1),
        evaluated_at=delayed,
        provenance=MarketDataProvenanceV1(
            "ANGEL_SMARTAPI",
            "India VIX",
            "NSE",
            "LIVE",
            delayed - timedelta(seconds=1),
            delayed,
            False,
            None,
            None,
        ),
        source_status="READY",
    )

    result = build_certified_shared_broader_context(
        nifty_observation=observation(
            "NIFTY",
            "NSE",
            25000.0,
            evaluated_at=delayed,
        ),
        sensex_observation=observation(
            "SENSEX",
            "BSE",
            80000.0,
            evaluated_at=delayed,
        ),
        evaluated_at=delayed,
        cross_market_evaluated_at=NOW,
        india_vix_capture=capture,
    )

    assert result.evaluated_at == delayed

    nifty_cross = (
        result.nifty_broader_market
        .cross_market_evidence[0]
    )
    sensex_cross = (
        result.sensex_broader_market
        .cross_market_evidence[0]
    )

    assert (
        "CROSS_MARKET_SOURCE_EVIDENCE_STALE"
        not in nifty_cross.blockers
    )
    assert (
        "CROSS_MARKET_SOURCE_EVIDENCE_STALE"
        not in sensex_cross.blockers
    )

    assert (
        result.nifty_broader_market
        .volatility_context
        .volatility_regime
        == "LOW"
    )
    assert (
        result.sensex_broader_market
        .volatility_context
        .volatility_regime
        == "LOW"
    )

    assert (
        "volatility source timestamp exceeds future tolerance"
        not in result.nifty_broader_market.blockers
    )
    assert (
        "volatility source timestamp exceeds future tolerance"
        not in result.sensex_broader_market.blockers
    )
