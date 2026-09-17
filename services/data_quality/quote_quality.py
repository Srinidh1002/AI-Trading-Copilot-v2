from services.contracts.market_quote_v1 import MarketQuoteV1
from services.data_quality.freshness import evaluate_quote_freshness
def evaluate_market_quote_quality(quote,**kwargs):
 if not isinstance(quote,MarketQuoteV1):raise TypeError("quote must be MarketQuoteV1.")
 return evaluate_quote_freshness(quote,**kwargs)
