"""
End-to-end live market analysis pipeline.

Read-only:
- Fetches market data
- Runs analytical engines
- Selects a strategy

It does not place orders.
"""

from services.live_multi_timeframe_data import (
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

from services.strategy_selector import (
    select_strategy,
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

        timeframes = (
            self.data_service.fetch_all(
                exchange=exchange,
                symboltoken=symboltoken,
                end_time=end_time,
            )
        )

        uppercase_timeframes = {
            timeframe: to_uppercase_ohlcv(df)
            for timeframe, df
            in timeframes.items()
        }

        # ---------------------------------
        # MULTI-TIMEFRAME ANALYSIS
        # ---------------------------------

        timeframe_analysis = (
            analyse_multi_timeframe(
                uppercase_timeframes
            )
        )

        # Use 5-minute timeframe for
        # immediate setup analysis.
        base_data = uppercase_timeframes["5m"]

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
        # PATTERN ANALYSIS
        # ---------------------------------

        lowercase_data = (
            to_lowercase_ohlcv(
                base_data
            )
        )

        candlestick_analysis = (
            analyse_patterns(
                lowercase_data
            )
        )

        chart_analysis = (
            analyse_chart_patterns(
                lowercase_data
            )
        )

        # ---------------------------------
        # STRATEGY SELECTION
        # ---------------------------------

        strategy_analysis = (
            select_strategy(
                regime=regime_analysis,
                timeframe=timeframe_analysis,
                technical=technical_analysis,
                candlestick=(
                    candlestick_analysis
                ),
                chart=chart_analysis,
                option=option_analysis,
            )
        )

        return {
            "timeframes": timeframes,
            "technical": technical_analysis,
            "timeframe": timeframe_analysis,
            "regime": regime_analysis,
            "candlestick": (
                candlestick_analysis
            ),
            "chart": chart_analysis,
            "strategy": strategy_analysis,
        }