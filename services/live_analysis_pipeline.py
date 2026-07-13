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

from services.volume_intelligence import (
    analyse_volume_intelligence,
)

from services.regime_aware_evidence import (
    evaluate_regime_aware_evidence,
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
        base_data = (
            uppercase_timeframes["5m"]
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
        # LOWERCASE DATA ADAPTER
        # ---------------------------------

        lowercase_data = (
            to_lowercase_ohlcv(
                base_data
            )
        )

        # ---------------------------------
        # CANDLESTICK / PRICE PATTERNS
        # ---------------------------------

        candlestick_analysis = (
            analyse_patterns(
                lowercase_data
            )
        )

        # ---------------------------------
        # VOLUME INTELLIGENCE
        # ---------------------------------

        volume_analysis = (
            analyse_volume_intelligence(
                lowercase_data,
                support=(
                    candlestick_analysis.get(
                        "support"
                    )
                ),
                resistance=(
                    candlestick_analysis.get(
                        "resistance"
                    )
                ),
            )
        )

        # ---------------------------------
        # CHART PATTERN ANALYSIS
        # ---------------------------------

        chart_analysis = (
            analyse_chart_patterns(
                lowercase_data
            )
        )

        # ---------------------------------
        # REGIME-AWARE EVIDENCE
        #
        # Observational only at this stage.
        # It does not yet alter strategy
        # selection or authorize a trade.
        # ---------------------------------

        regime_aware_evidence = (
            evaluate_regime_aware_evidence(
                regime=regime_analysis,
                timeframe=timeframe_analysis,
                technical=technical_analysis,
                candlestick=(
                    candlestick_analysis
                ),
                chart=chart_analysis,
                volume=volume_analysis,
            )
        )

        # ---------------------------------
        # STRATEGY SELECTION
        #
        # Existing behaviour is intentionally
        # preserved. Regime-aware evidence
        # is not passed into the selector yet.
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
                regime_aware_evidence=(
                    regime_aware_evidence
                ),
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
            "volume": volume_analysis,
            "regime_aware_evidence": (
                regime_aware_evidence
            ),
            "strategy": strategy_analysis,
        }