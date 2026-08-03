"""Provider-free shared NIFTY/SENSEX canonical broader-market binding."""
from __future__ import annotations

from datetime import datetime

from services.broader_market_intelligence.integration import build_broader_market_intelligence
from services.contracts.certified_shared_market_context_v1 import CertifiedSharedMarketContextV1
from services.contracts.india_vix_capture_result_v1 import IndiaVixCaptureResultV1
from services.analysis.india_vix_normalizer import normalize_india_vix_capture
from services.analysis.shared_external_market_context import build_shared_external_market_context
from services.market.angel_live_observation_normalizer import AngelLiveMarketObservationV1


CORRELATION_TIMEFRAME = "5m"
_IDENTITIES = (("NIFTY", "NSE"), ("SENSEX", "BSE"))


def _aware(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at")
    return value


def _series(observation: AngelLiveMarketObservationV1, identity: tuple[str, str], evaluated_at: datetime):
    if type(observation) is not AngelLiveMarketObservationV1:
        raise TypeError("observation")
    spot = observation.spot
    if (spot.underlying_symbol, spot.exchange) != identity or spot.evaluated_at != evaluated_at:
        raise ValueError("observation identity or evaluation boundary")
    return {series.timeframe: series for series in observation.candle_series}


def build_certified_shared_broader_context(*, nifty_observation: AngelLiveMarketObservationV1, sensex_observation: AngelLiveMarketObservationV1, evaluated_at: datetime, india_vix_capture: IndiaVixCaptureResultV1|None=None, capture_diagnostics: dict | None = None) -> CertifiedSharedMarketContextV1:
    """Build both primary canonical results from already-normalized 5m candles."""
    evaluated_at = _aware(evaluated_at)
    nifty = _series(nifty_observation, _IDENTITIES[0], evaluated_at)
    sensex = _series(sensex_observation, _IDENTITIES[1], evaluated_at)
    cycle_id = f"shared-broader:{evaluated_at.isoformat()}"
    blockers: tuple[str, ...] = (); vix=normalize_india_vix_capture(india_vix_capture) if india_vix_capture is not None else (None,None); external=build_shared_external_market_context(cycle_id=cycle_id, evaluated_at=evaluated_at)
    nifty_result = sensex_result = None
    if CORRELATION_TIMEFRAME not in nifty or CORRELATION_TIMEFRAME not in sensex:
        blockers = ("CORRELATION_TIMEFRAME_UNAVAILABLE_5M",)
    else:
        nifty_series, sensex_series = nifty[CORRELATION_TIMEFRAME], sensex[CORRELATION_TIMEFRAME]
        prefix = f"shared-broader:{nifty_series.series_id}:{sensex_series.series_id}:{evaluated_at.isoformat()}"
        nifty_result = build_broader_market_intelligence(
            primary_series=nifty_series, related_series=sensex_series, breadth_snapshot=None, volatility_snapshot=vix[0], volatility_context_id=f"{prefix}:nifty-vix" if vix[0] else None,
            created_at=evaluated_at, cross_market_evidence_id=f"{prefix}:nifty-cross", result_id=f"{prefix}:nifty",
        )
        sensex_result = build_broader_market_intelligence(
            primary_series=sensex_series, related_series=nifty_series, breadth_snapshot=None, volatility_snapshot=vix[1], volatility_context_id=f"{prefix}:sensex-vix" if vix[1] else None,
            created_at=evaluated_at, cross_market_evidence_id=f"{prefix}:sensex-cross", result_id=f"{prefix}:sensex",
        )
    timestamps = {"NIFTY_5M": nifty[CORRELATION_TIMEFRAME].created_at, "SENSEX_5M": sensex[CORRELATION_TIMEFRAME].created_at} if CORRELATION_TIMEFRAME in nifty and CORRELATION_TIMEFRAME in sensex else {}
    return CertifiedSharedMarketContextV1(
        cycle_id=cycle_id, evaluated_at=evaluated_at,
        nifty_candle_series=nifty, sensex_candle_series=sensex,
        nifty_broader_market=nifty_result, sensex_broader_market=sensex_result,
        source_timestamps=timestamps, india_vix_capture=india_vix_capture, shared_external_context=external, blockers=blockers,
        cache_metadata={"india_vix_normalization": {"nifty_snapshot_id": vix[0].volatility_snapshot_id if vix[0] else None, "sensex_snapshot_id": vix[1].volatility_snapshot_id if vix[1] else None}, "capture_diagnostics": capture_diagnostics or {}},
    )
