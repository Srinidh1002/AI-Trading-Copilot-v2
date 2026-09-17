"""Canonical, side-effect-free orchestration from MarketSnapshot to analysis."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.analysis.price_market_structure_engine import PriceMarketStructureEngine
from services.chart_pattern_analyzer import analyse_chart_patterns
from services.contracts.analysis_result_v1 import (
    AnalysisResultV1,
    DirectionalBias,
    EvidenceSection,
    EvidenceSignal,
    EvidenceStatus,
    MarketRegime,
)
from services.contracts.market_snapshot_v1 import DataStatus, MarketSnapshotV1
from services.market_regime_engine import analyze_market_regime
from services.multi_timeframe_analyzer import analyse_multi_timeframe
from services.option_ai import option_score
from services.pattern_analyzer import analyse_patterns
from services.technical_analyzer import analyse_technical
from services.volume_intelligence import analyse_volume_intelligence

from .adapters import (
    bounded_score,
    canonical_timeframes_to_frames,
    error_evidence,
    evidence_from_mapping,
    evidence_signal,
    multi_timeframe_summary,
    normalize_bias,
    snapshot_data_quality,
    unavailable_evidence,
)


def _now(snapshot: MarketSnapshotV1) -> datetime:
    return snapshot.captured_at


@dataclass(frozen=True, slots=True)
class CanonicalAnalysisDependencies:
    """Pure/injected analysis dependencies; none may fetch or persist data."""

    clock: Callable[[MarketSnapshotV1], datetime] = _now
    technical_analyzer: Callable[[Any], Mapping[str, Any]] = analyse_technical
    multi_timeframe_analyzer: Callable[[Mapping[str, Any]], Mapping[str, Any]] = analyse_multi_timeframe
    candlestick_analyzer: Callable[[Any], Mapping[str, Any]] = analyse_patterns
    chart_analyzer: Callable[[Any], Mapping[str, Any]] = analyse_chart_patterns
    volume_analyzer: Callable[..., Mapping[str, Any]] = analyse_volume_intelligence
    market_structure_analyzer: Callable[[Mapping[str, Any]], Mapping[str, Any]] = PriceMarketStructureEngine.analyze
    market_regime_analyzer: Callable[[Mapping[str, Any]], Mapping[str, Any]] = analyze_market_regime
    option_analyzer: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] = option_score


@dataclass(slots=True)
class CanonicalAnalysisPipeline:
    dependencies: CanonicalAnalysisDependencies = field(
        default_factory=CanonicalAnalysisDependencies
    )

    def analyse(self, snapshot: MarketSnapshotV1) -> AnalysisResultV1:
        if not isinstance(snapshot, MarketSnapshotV1):
            raise TypeError("snapshot must be a MarketSnapshotV1.")
        if not snapshot.validation_passed or snapshot.is_stale:
            return self._blocked_market_analysis(snapshot)

        frames = canonical_timeframes_to_frames(snapshot)
        if "5m" not in frames or frames["5m"].empty:
            return self._missing_primary_timeframe(snapshot)

        errors: dict[str, tuple[str, ...]] = {}
        technical_payload = self._run(
            "technical", errors, self.dependencies.technical_analyzer, frames["5m"]
        )
        if technical_payload is None:
            return self._engine_failure(snapshot, errors)
        technical = evidence_from_mapping(technical_payload, signal_key="trend")

        timeframe_payload = self._run(
            "multi_timeframe", errors,
            self.dependencies.multi_timeframe_analyzer, frames,
        ) or {}
        multi_timeframe = multi_timeframe_summary(timeframe_payload, set(frames))

        lower = frames["5m"]
        candlestick_payload = self._run(
            "candlestick", errors, self.dependencies.candlestick_analyzer, lower
        )
        candlestick = self._mapping_evidence(candlestick_payload, errors, "candlestick")

        chart_payload = self._run("chart", errors, self.dependencies.chart_analyzer, lower)
        structure_payload = self._run(
            "market_structure", errors, self.dependencies.market_structure_analyzer,
            {"history": lower},
        )
        market_structure = self._structure_evidence(structure_payload, chart_payload, errors)

        volume_payload = self._run(
            "volume", errors, self.dependencies.volume_analyzer, lower,
            support=(candlestick_payload or {}).get("support"),
            resistance=(candlestick_payload or {}).get("resistance"),
        )
        volume = self._volume_evidence(volume_payload, errors)

        regime_input = self._regime_input(technical_payload, snapshot)
        regime_payload = self._run(
            "market_regime", errors, self.dependencies.market_regime_analyzer, regime_input
        ) or {}
        market_regime = self._canonical_regime(regime_payload.get("regime"))

        options = self._options_evidence(snapshot, errors)
        institutional = self._institutional_evidence(snapshot)
        volatility = self._volatility_evidence(snapshot)
        context = unavailable_evidence("No canonical event/news context was supplied.")

        bias, resolved, contradictions = self._resolve_direction(
            technical, market_structure, candlestick, volume, multi_timeframe
        )
        return AnalysisResultV1(
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            created_at=self.dependencies.clock(snapshot),
            market_timestamp=snapshot.market_timestamp,
            market_regime=market_regime,
            directional_bias=bias,
            direction_resolved=resolved,
            trend_strength=bounded_score(regime_payload.get("trend_strength")),
            volatility_state=self._volatility_state(snapshot),
            market_session=snapshot.market_session,
            multi_timeframe=multi_timeframe,
            technical=technical,
            market_structure=market_structure,
            candlestick=candlestick,
            volume=volume,
            options=options,
            institutional=institutional,
            volatility=volatility,
            context=context,
            technical_score=technical.score,
            structure_score=market_structure.score,
            candlestick_score=candlestick.score,
            volume_score=volume.score,
            options_score=options.score,
            institutional_score=institutional.score,
            volatility_score=volatility.score,
            data_quality_score=snapshot_data_quality(snapshot),
            supporting_reasons=tuple(
                technical.reasons + market_structure.reasons + candlestick.reasons
            ),
            contradictions=contradictions,
            missing_inputs=tuple(snapshot.missing_sources),
            warnings=tuple(snapshot.warnings),
            engine_errors=errors,
            source_timestamps={"market": snapshot.market_timestamp.isoformat()},
            trace_metadata={"pipeline": "canonical_analysis.v1"},
        )

    @staticmethod
    def _run(name: str, errors: dict[str, tuple[str, ...]], func: Callable[..., Mapping[str, Any]], *args: Any, **kwargs: Any) -> Mapping[str, Any] | None:
        try:
            result = func(*args, **kwargs)
            if not isinstance(result, Mapping):
                raise TypeError("Engine result must be a mapping.")
            return result
        except Exception as exc:
            errors[name] = (f"{type(exc).__name__}: {exc}",)
            return None

    def _blocked_market_analysis(self, snapshot: MarketSnapshotV1) -> AnalysisResultV1:
        reason = "Snapshot validation failed." if not snapshot.validation_passed else "Snapshot is stale."
        return AnalysisResultV1(
            snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol,
            created_at=self.dependencies.clock(snapshot), market_timestamp=snapshot.market_timestamp,
            market_session=snapshot.market_session,
            missing_inputs=tuple(snapshot.missing_sources),
            warnings=tuple(snapshot.warnings),
            engine_errors={"market_data": tuple(snapshot.critical_errors or (reason,))},
            trace_metadata={"pipeline": "canonical_analysis.v1"},
        )

    def _missing_primary_timeframe(self, snapshot: MarketSnapshotV1) -> AnalysisResultV1:
        return AnalysisResultV1(
            snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol,
            created_at=self.dependencies.clock(snapshot), market_timestamp=snapshot.market_timestamp,
            market_session=snapshot.market_session,
            missing_inputs=("5m",),
            engine_errors={"market_data": ("Required 5m timeframe is unavailable.",)},
            trace_metadata={"pipeline": "canonical_analysis.v1"},
        )

    def _engine_failure(self, snapshot: MarketSnapshotV1, errors: dict[str, tuple[str, ...]]) -> AnalysisResultV1:
        return AnalysisResultV1(
            snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol,
            created_at=self.dependencies.clock(snapshot), market_timestamp=snapshot.market_timestamp,
            market_session=snapshot.market_session, engine_errors=errors,
            trace_metadata={"pipeline": "canonical_analysis.v1"},
        )

    @staticmethod
    def _mapping_evidence(payload: Mapping[str, Any] | None, errors: Mapping[str, tuple[str, ...]], name: str) -> EvidenceSection:
        return evidence_from_mapping(payload) if payload is not None else error_evidence(Exception(errors[name][0]))

    @staticmethod
    def _structure_evidence(structure: Mapping[str, Any] | None, chart: Mapping[str, Any] | None, errors: Mapping[str, tuple[str, ...]]) -> EvidenceSection:
        if structure is None:
            return error_evidence(Exception(errors["market_structure"][0]))
        reasons = list(chart.get("patterns", ())) if chart else []
        reasons.append(str(structure.get("structure", "UNKNOWN")))
        payload = dict(structure)
        payload["reasons"] = reasons
        payload["signal"] = structure.get("trend", chart.get("signal") if chart else "UNKNOWN")
        payload["score"] = structure.get("confidence")
        return evidence_from_mapping(payload)

    @staticmethod
    def _volume_evidence(payload: Mapping[str, Any] | None, errors: Mapping[str, tuple[str, ...]]) -> EvidenceSection:
        if payload is None:
            return error_evidence(Exception(errors["volume"][0]))
        payload = dict(payload)
        payload["signal"] = payload.get("bias")
        payload["score"] = 100 if payload.get("volume_spike") else 0
        payload["reasons"] = payload.get("bullish_evidence", ()) + payload.get("bearish_evidence", ())
        return evidence_from_mapping(payload)

    def _options_evidence(self, snapshot: MarketSnapshotV1, errors: dict[str, tuple[str, ...]]) -> EvidenceSection:
        if snapshot.option_chain_status != DataStatus.VALID.value:
            return unavailable_evidence("Option-chain evidence is not fresh and valid.", status=snapshot.option_chain_status)
        if not isinstance(snapshot.option_chain_data, Mapping):
            return unavailable_evidence("Option-chain payload is unavailable.")
        payload = self._run("options", errors, self.dependencies.option_analyzer, snapshot.symbol, snapshot.option_chain_data)
        if payload is None:
            return error_evidence(Exception(errors["options"][0]))
        payload = dict(payload)
        payload["signal"] = "BULLISH" if payload.get("bull_score", 0) > payload.get("bear_score", 0) else "BEARISH" if payload.get("bear_score", 0) > payload.get("bull_score", 0) else "NEUTRAL"
        payload["score"] = abs(float(payload.get("score", 0)))
        return evidence_from_mapping(payload)

    @staticmethod
    def _institutional_evidence(snapshot: MarketSnapshotV1) -> EvidenceSection:
        if snapshot.fii_dii_status != DataStatus.VALID.value:
            return unavailable_evidence("Institutional evidence is not fresh and valid.", status=snapshot.fii_dii_status)
        return EvidenceSection(status=EvidenceStatus.PARTIAL, signal=EvidenceSignal.NEUTRAL, metadata=dict(snapshot.fii_dii_data or {}))

    @staticmethod
    def _volatility_evidence(snapshot: MarketSnapshotV1) -> EvidenceSection:
        if snapshot.india_vix_status != DataStatus.VALID.value:
            return unavailable_evidence("India VIX evidence is not fresh and valid.", status=snapshot.india_vix_status)
        value = snapshot.india_vix_value
        signal = EvidenceSignal.NEUTRAL
        warning = ()
        if value is not None and value >= 28:
            warning = ("India VIX is elevated.",)
        return EvidenceSection(status=EvidenceStatus.VALID, signal=signal, score=bounded_score(value), warnings=warning, metadata={"india_vix": value})

    @staticmethod
    def _regime_input(technical: Mapping[str, Any], snapshot: MarketSnapshotV1) -> dict[str, Any]:
        indicators = dict(technical.get("indicators", {}))
        return {
            "CURRENT_PRICE": snapshot.ltp, "EMA20": indicators.get("ema20"),
            "EMA50": indicators.get("ema50"), "EMA200": indicators.get("ema200"),
            "RSI": indicators.get("rsi"), "ADX": None, "ATR": indicators.get("atr"),
            "INDIA_VIX": snapshot.india_vix_value,
        }

    @staticmethod
    def _canonical_regime(value: Any) -> str:
        value = str(value or "").upper()
        if value in {"TRENDING_BULL", "TRENDING_BEAR", "GAP_UP_TREND_DAY", "GAP_DOWN_TREND_DAY"}:
            return MarketRegime.TRENDING.value
        if value in {"BREAKOUT", "BREAKDOWN"}:
            return MarketRegime.BREAKOUT_TRANSITION.value
        if value == "HIGH_VOLATILITY":
            return MarketRegime.HIGH_VOLATILITY.value
        if value in {"RANGE_BOUND", "SIDEWAYS", "MEAN_REVERSION"}:
            return MarketRegime.RANGING.value
        return MarketRegime.UNCERTAIN.value

    @staticmethod
    def _volatility_state(snapshot: MarketSnapshotV1) -> str:
        return "ELEVATED" if snapshot.india_vix_value is not None and snapshot.india_vix_value >= 28 else "UNKNOWN"

    @staticmethod
    def _resolve_direction(technical: EvidenceSection, structure: EvidenceSection, candlestick: EvidenceSection, volume: EvidenceSection, multi_timeframe: Any) -> tuple[str, bool, tuple[str, ...]]:
        signals = [technical.signal, structure.signal, candlestick.signal, volume.signal]
        bullish, bearish = signals.count(EvidenceSignal.BULLISH.value), signals.count(EvidenceSignal.BEARISH.value)
        conflicts: list[str] = []
        if multi_timeframe.alignment == "CONFLICTED":
            conflicts.append("Multi-timeframe evidence is conflicted.")
        if bullish and bearish:
            conflicts.append("Analysis evidence contains opposing directional signals.")
        if conflicts:
            return DirectionalBias.CONFLICTED.value, False, tuple(conflicts)
        if bullish > bearish and bullish:
            return DirectionalBias.BULLISH.value, True, ()
        if bearish > bullish and bearish:
            return DirectionalBias.BEARISH.value, True, ()
        return DirectionalBias.NEUTRAL.value, True, ()
