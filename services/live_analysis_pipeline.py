"""End-to-end read-only live market analysis pipeline."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from services.analysis.price_market_structure_engine import (
    PriceMarketStructureEngine,
)
from services.chart_pattern_analyzer import (
    analyse_chart_patterns,
)
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)
from services.market_data_adapter import (
    to_lowercase_ohlcv,
    to_uppercase_ohlcv,
)
from services.market_regime_analyzer import (
    analyse_market_regime,
)
from services.multi_timeframe_analyzer import (
    analyse_multi_timeframe,
)
from services.pattern_analyzer import analyse_patterns
from services.regime_aware_evidence import (
    evaluate_regime_aware_evidence,
)
from services.regime_indicator_builder import (
    add_regime_indicators,
)
from services.strategy_selector import select_strategy
from services.technical_analyzer import analyse_technical
from services.volume_intelligence import (
    analyse_volume_intelligence,
)


TIMEFRAMES = (
    "5m",
    "15m",
    "1h",
    "1d",
)


class LiveAnalysisPipeline:
    def __init__(self, data_service=None):
        self.data_service = (
            data_service
            if data_service is not None
            else LiveMultiTimeframeData()
        )

    @staticmethod
    def _normalize_timeframes(
        timeframes: object,
    ) -> dict[str, pd.DataFrame]:
        if not isinstance(timeframes, Mapping):
            raise TypeError(
                "multi-timeframe data service must return a mapping"
            )

        normalized: dict[str, pd.DataFrame] = {}

        for timeframe in TIMEFRAMES:
            data = timeframes.get(timeframe)

            if data is None:
                continue

            if not isinstance(data, pd.DataFrame):
                raise TypeError(
                    f"{timeframe} timeframe must be a pandas DataFrame"
                )

            if data.empty:
                continue

            try:
                normalized[timeframe] = to_uppercase_ohlcv(
                    data,
                    require_complete=True,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{timeframe} timeframe has invalid OHLCV schema: "
                    f"{exc}"
                ) from exc

        return normalized

    def analyse(
        self,
        exchange,
        symboltoken,
        option_analysis=None,
        end_time=None,
        captured_timeframes=None,
    ):
        capture = captured_timeframes
        timeframes = (capture["dataframes"] if isinstance(capture, Mapping) and "dataframes" in capture else capture) if capture is not None else self.data_service.fetch_all(exchange=exchange, symboltoken=symboltoken, end_time=end_time)

        uppercase_timeframes = self._normalize_timeframes(
            timeframes
        )

        base_data = uppercase_timeframes.get("5m")

        if base_data is None or base_data.empty:
            raise ValueError(
                "5m timeframe is unavailable or empty"
            )

        timeframe_analysis = analyse_multi_timeframe(
            uppercase_timeframes
        )

        technical_analysis = analyse_technical(
            base_data
        )

        regime_data = add_regime_indicators(
            base_data
        )

        regime_analysis = analyse_market_regime(
            regime_data
        )

        lowercase_data = to_lowercase_ohlcv(
            base_data,
            require_complete=True,
        )

        candlestick_analysis = analyse_patterns(
            lowercase_data
        )

        volume_analysis = analyse_volume_intelligence(
            lowercase_data,
            support=candlestick_analysis.get("support"),
            resistance=candlestick_analysis.get(
                "resistance"
            ),
        )

        chart_analysis = analyse_chart_patterns(
            lowercase_data
        )

        market_structure_analysis = (
            PriceMarketStructureEngine.analyze(
                {
                    "history": lowercase_data,
                }
            )
        )

        regime_aware_evidence = (
            evaluate_regime_aware_evidence(
                regime=regime_analysis,
                timeframe=timeframe_analysis,
                technical=technical_analysis,
                candlestick=candlestick_analysis,
                chart=chart_analysis,
                volume=volume_analysis,
            )
        )

        strategy_analysis = select_strategy(
            regime=regime_analysis,
            timeframe=timeframe_analysis,
            technical=technical_analysis,
            candlestick=candlestick_analysis,
            chart=chart_analysis,
            option=option_analysis,
            regime_aware_evidence=(
                regime_aware_evidence
            ),
        )

        result = {
            "timeframes": timeframes,
            "technical": technical_analysis,
            "timeframe": timeframe_analysis,
            "regime": regime_analysis,
            "candlestick": candlestick_analysis,
            "chart": chart_analysis,
            "volume": volume_analysis,
            "regime_aware_evidence": (
                regime_aware_evidence
            ),
            "strategy": strategy_analysis,
            "market_structure": (
                market_structure_analysis
            ),
        }
        if capture is not None: result["captured_timeframes"] = capture
        return result
