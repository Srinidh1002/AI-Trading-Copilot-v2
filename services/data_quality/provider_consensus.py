from datetime import datetime,timezone
from statistics import median
from services.contracts.market_quote_v1 import MarketQuoteV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_data_freshness_policy_v1 import DEFAULT_MARKET_DATA_FRESHNESS_POLICY
def evaluate_provider_quote_consensus(quotes,*,policy=DEFAULT_MARKET_DATA_FRESHNESS_POLICY,clock=None,quality_result_id_factory=None):
 values=tuple(quotes);now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not values:return MarketDataQualityResultV1((quality_result_id_factory or (lambda:"quality"))(),now,"PROVIDER_CONSENSUS","EMPTY",item_count=0,blockers=("quotes_missing",))
 if any(not isinstance(q,MarketQuoteV1) for q in values) or len({(q.underlying_symbol,q.exchange) for q in values})!=1:return MarketDataQualityResultV1((quality_result_id_factory or (lambda:"quality"))(),now,"PROVIDER_CONSENSUS","MALFORMED",item_count=len(values),blockers=("inconsistent_quotes",))
 prices=[q.last_price for q in values];reference=median(prices);bps=max(abs(p-reference)/reference*10000 for p in prices) if reference else 0;status="CONFLICTING" if bps>policy.provider_disagreement_block_bps else "VALID_WITH_WARNINGS" if bps>policy.provider_disagreement_warning_bps else "VALID";b=("provider_disagreement",) if status=="CONFLICTING" else ();w=("provider_disagreement",) if status=="VALID_WITH_WARNINGS" else ();q=values[0]
 return MarketDataQualityResultV1((quality_result_id_factory or (lambda:"quality"))(),now,"PROVIDER_CONSENSUS",status,q.underlying_symbol,q.exchange,source_provider=None,item_count=len(values),valid_item_count=len(values),provider_count=len({q.provenance.provider for q in values}),disagreement_bps=bps,blockers=b,warnings=w)
