"""
End-to-end live market analysis pipeline.

Read-only:
- Fetches market data
- Runs analytical engines
- Calculates volume intelligence
- Routes evidence according to the live market regime
- Selects a strategy

It does not place orders.
"""

from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)

from services.market_data_adapter import (
    to_uppercase_ohlcv,
    to_lowercase_ohlcv,
)

from services.regime_indicator_builder import (
    add_regime_indicators,
)

from services.technical_analyzer import (
    analyse_technical,
)

from services.multi_timeframe_analyzer import (
    analyse_multi_timeframe,
)

from services.market_regime_analyzer import (
    analyse_market_regime,
)

from services.pattern_analyzer import (
    analyse_patterns,
)

from services.chart_pattern_analyzer import (
    analyse_chart_patterns,
)

from services.volume_intelligence import (
    analyse_volume_intelligence,
)

from services.regime_aware_evidence import (
    evaluate_regime_aware_evidence,
)

from services.strategy_selector import (
    select_strategy,
)
from services.analysis.price_market_structure_engine import (
    PriceMarketStructureEngine,
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

    def analyse(
        self,
        exchange,
        symboltoken,
        option_analysis=None,
        end_time=None,
    ):

        # ---------------------------------
        # FETCH ALL TIMEFRAMES
        # ---------------------------------

        timeframes = self.data_service.fetch_all(
            exchange=exchange,
            symboltoken=symboltoken,
            end_time=end_time,
        )

        uppercase_timeframes = {
            timeframe: to_uppercase_ohlcv(df)
            for timeframe, df in timeframes.items()
            if df is not None and not df.empty
        }

        base_data = uppercase_timeframes.get("5m")

        if base_data is None:
            raise ValueError(
                "5m timeframe unavailable."
            )

        # ---------------------------------
        # MULTI-TIMEFRAME ANALYSIS
        # ---------------------------------

        timeframe_analysis = (
            analyse_multi_timeframe(
                uppercase_timeframes
            )
        )

        # ---------------------------------
        # TECHNICAL ANALYSIS
        # ---------------------------------

        technical_analysis = (
            analyse_technical(
                base_data
            )
        )

        # ---------------------------------
        # MARKET REGIME
        # ---------------------------------

        regime_data = (
            add_regime_indicators(
                base_data
            )
        )

        regime_analysis = (
            analyse_market_regime(
                regime_data
            )
        )

        # ---------------------------------
        # LOWERCASE DATA
        # ---------------------------------

        lowercase_data = (
            to_lowercase_ohlcv(
                base_data
            )
        )

        # ---------------------------------
        # CANDLESTICK
        # ---------------------------------

        candlestick_analysis = (
            analyse_patterns(
                lowercase_data
            )
        )

        # ---------------------------------
        # VOLUME
        # ---------------------------------

        volume_analysis = (
            analyse_volume_intelligence(
                lowercase_data,
                support=candlestick_analysis.get(
                    "support"
                ),
                resistance=candlestick_analysis.get(
                    "resistance"
                ),
            )
        )

        # ---------------------------------
        # CHART
        # ---------------------------------

        chart_analysis = (
            analyse_chart_patterns(
                lowercase_data
            )
        )
        # ---------------------------------
        # MARKET STRUCTURE
        # ---------------------------------

        market_structure_analysis = (
            PriceMarketStructureEngine.analyze(
                {
                    "history": lowercase_data,
                }
            )
        )

        # ---------------------------------
        # EVIDENCE
        # ---------------------------------

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

        # ---------------------------------
        # STRATEGY
        # ---------------------------------

        strategy_analysis = (
            select_strategy(
                regime=regime_analysis,
                timeframe=timeframe_analysis,
                technical=technical_analysis,
                candlestick=candlestick_analysis,
                chart=chart_analysis,
                option=option_analysis,
                regime_aware_evidence=regime_aware_evidence,
            )
        )

        return {
            "timeframes": timeframes,
            "technical": technical_analysis,
            "timeframe": timeframe_analysis,
            "regime": regime_analysis,
            "candlestick": candlestick_analysis,
            "chart": chart_analysis,
            "volume": volume_analysis,
            "regime_aware_evidence": regime_aware_evidence,
            "strategy": strategy_analysis,
            "market_structure": market_structure_analysis,
        }
