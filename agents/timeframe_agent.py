from models.timeframe_state import TimeframeState
from services.multi_timeframe_analyzer import analyse_multi_timeframe


class TimeframeAgent:

    def analyse(self, timeframes):

        result = analyse_multi_timeframe(timeframes)

        return TimeframeState(
            overall_trend=result["overall_trend"],
            confidence=result["confidence"],
            alignment=result["alignment"],
            timeframe_results=result["timeframe_results"],
            reasons=result["reasons"],
        )