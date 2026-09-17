from datetime import datetime,timezone
from services.contracts.market_candle_v1 import MarketCandleV1
from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_data_freshness_policy_v1 import DEFAULT_MARKET_DATA_FRESHNESS_POLICY
from services.data_quality.freshness import evaluate_candle_freshness
def evaluate_market_candle_quality(candle,**kwargs):
 if not isinstance(candle,MarketCandleV1):raise TypeError("candle must be MarketCandleV1.")
 return evaluate_candle_freshness(candle,**kwargs)
def evaluate_market_candle_series_quality(series,*,policy=DEFAULT_MARKET_DATA_FRESHNESS_POLICY,clock=None,quality_result_id_factory=None):
 if not isinstance(series,MarketCandleSeriesV1):raise TypeError("series must be MarketCandleSeriesV1.")
 now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not series.candles:return MarketDataQualityResultV1((quality_result_id_factory or (lambda:"quality"))(),now,"CANDLE_SERIES","EMPTY",series.underlying_symbol,series.exchange,series.timeframe,item_count=0,blockers=("empty_series",))
 latest=evaluate_candle_freshness(series.candles[-1],policy=policy,clock=lambda:now,quality_result_id_factory=quality_result_id_factory)
 return MarketDataQualityResultV1(latest.quality_result_id,now,"CANDLE_SERIES",latest.quality_status,series.underlying_symbol,series.exchange,series.timeframe,age_seconds=latest.age_seconds,freshness_threshold_seconds=latest.freshness_threshold_seconds,item_count=len(series.candles),valid_item_count=len(series.candles) if latest.quality_status=="VALID" else 0,invalid_item_count=0 if latest.quality_status=="VALID" else 1,incomplete_item_count=sum(not c.is_complete for c in series.candles),blockers=latest.blockers,warnings=latest.warnings)
