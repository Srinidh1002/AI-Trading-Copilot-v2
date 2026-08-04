"""Isolated, single-pass orchestration for canonical broader-market evidence."""
from __future__ import annotations
from datetime import datetime
from typing import Callable
from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
from services.contracts.volatility_snapshot_v1 import VolatilitySnapshotV1
from services.contracts.broader_market_intelligence_policy_v1 import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,BroaderMarketIntelligencePolicyV1
from .correlation import evaluate_cross_market_correlation
from .breadth import evaluate_market_breadth
from .volatility import evaluate_volatility_context
from .evaluator import evaluate_broader_market_intelligence
def build_broader_market_intelligence(*,primary_series:MarketCandleSeriesV1,related_series:MarketCandleSeriesV1,breadth_snapshot:MarketBreadthSnapshotV1|None=None,volatility_snapshot:VolatilitySnapshotV1|None=None,policy:BroaderMarketIntelligencePolicyV1=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,created_at:datetime,cross_market_evidence_id:str,breadth_evidence_id:str|None=None,volatility_context_id:str|None=None,result_id:str,correlation_evaluator:Callable=evaluate_cross_market_correlation,breadth_evaluator:Callable=evaluate_market_breadth,volatility_evaluator:Callable=evaluate_volatility_context,aggregate_evaluator:Callable=evaluate_broader_market_intelligence):
 if not isinstance(primary_series,MarketCandleSeriesV1) or not isinstance(related_series,MarketCandleSeriesV1):raise TypeError("series inputs must be MarketCandleSeriesV1")
 if breadth_snapshot is not None and not isinstance(breadth_snapshot,MarketBreadthSnapshotV1):raise TypeError("breadth_snapshot must be MarketBreadthSnapshotV1 or None")
 if volatility_snapshot is not None and not isinstance(volatility_snapshot,VolatilitySnapshotV1):raise TypeError("volatility_snapshot must be VolatilitySnapshotV1 or None")
 if not isinstance(policy,BroaderMarketIntelligencePolicyV1):raise TypeError("policy must be a BroaderMarketIntelligencePolicyV1")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(cross_market_evidence_id,str) or not cross_market_evidence_id.strip() or not isinstance(result_id,str) or not result_id.strip():raise ValueError("required IDs must be non-empty")
 if (breadth_snapshot is None)!=(breadth_evidence_id is None):raise ValueError("breadth snapshot and evidence ID must be supplied together")
 if (volatility_snapshot is None)!=(volatility_context_id is None):raise ValueError("volatility snapshot and context ID must be supplied together")
 if breadth_snapshot and (breadth_snapshot.underlying_symbol,breadth_snapshot.exchange)!=(primary_series.underlying_symbol,primary_series.exchange):raise ValueError("breadth identity must match primary series")
 if volatility_snapshot and (volatility_snapshot.underlying_symbol,volatility_snapshot.exchange)!=(primary_series.underlying_symbol,primary_series.exchange):raise ValueError("volatility identity must match primary series")
 if any(not callable(x) for x in (correlation_evaluator,breadth_evaluator,volatility_evaluator,aggregate_evaluator)):raise TypeError("evaluator dependencies must be callable")
 correlation=correlation_evaluator(primary_series=primary_series,related_series=related_series,policy=policy,created_at=created_at,evidence_id=cross_market_evidence_id)
 breadth=breadth_evaluator(breadth_snapshot=breadth_snapshot,policy=policy,created_at=created_at,evidence_id=breadth_evidence_id) if breadth_snapshot else None
 volatility=volatility_evaluator(volatility_snapshot=volatility_snapshot,policy=policy,created_at=created_at,context_id=volatility_context_id) if volatility_snapshot else None
 return aggregate_evaluator(underlying_symbol=primary_series.underlying_symbol,exchange=primary_series.exchange,cross_market_evidence=(correlation,),breadth_evidence=breadth,volatility_context=volatility,policy=policy,created_at=created_at,result_id=result_id)
