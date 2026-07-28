"""Static provider mapping evidence. This module never imports providers."""
from services.contracts.provider_market_mapping_v1 import ProviderMarketMappingV1
from services.core.market_universe import CANONICAL_MARKET_IDENTITIES,resolve_market_identity
_MAPPINGS=tuple(
 ProviderMarketMappingV1(provider,symbol,exchange,
  "SUPPORTED" if (provider,symbol)==("NSE_OPTION_CHAIN","NIFTY") else "UNKNOWN",
  "NIFTY" if (provider,symbol)==("NSE_OPTION_CHAIN","NIFTY") else None,
  "NSE" if (provider,symbol)==("NSE_OPTION_CHAIN","NIFTY") else None,
  "EXISTING_RUNTIME" if provider=="NSE_OPTION_CHAIN" else "AUDIT_CONFIRMED",
  () if (provider,symbol)==("NSE_OPTION_CHAIN","NIFTY") else ("No authoritative static provider symbol exists in repository evidence.",))
 for provider in ("YFINANCE","ANGEL_SMARTAPI","NSE_OPTION_CHAIN")
 for symbol,exchange in CANONICAL_MARKET_IDENTITIES)
def list_provider_market_mappings(provider=None):
 if provider is None:return _MAPPINGS
 if not isinstance(provider,str) or provider.upper() not in {"YFINANCE","ANGEL_SMARTAPI","NSE_OPTION_CHAIN"}:raise ValueError("Unknown provider.")
 return tuple(v for v in _MAPPINGS if v.provider==provider.upper())
def get_provider_market_mapping(provider,underlying_symbol,exchange=None):
 pair=resolve_market_identity(underlying_symbol,exchange); entries=list_provider_market_mappings(provider)
 return next(v for v in entries if (v.underlying_symbol,v.exchange)==pair)
def resolve_provider_symbol(provider,underlying_symbol,exchange=None):
 value=get_provider_market_mapping(provider,underlying_symbol,exchange)
 if value.mapping_status!="SUPPORTED":raise ValueError("Provider mapping is not supported.")
 return value.provider_symbol
def resolve_canonical_identity_from_provider_symbol(provider,provider_symbol,provider_exchange=None):
 if not isinstance(provider_symbol,str) or not provider_symbol:raise ValueError("provider_symbol is required.")
 matches=[v for v in list_provider_market_mappings(provider) if v.mapping_status=="SUPPORTED" and v.provider_symbol==provider_symbol and (provider_exchange is None or v.provider_exchange==provider_exchange)]
 if len(matches)!=1:raise ValueError("Provider symbol is unknown or ambiguous.")
 return matches[0].underlying_symbol,matches[0].exchange
def provider_supports_market(provider,underlying_symbol,exchange=None):
 try:return get_provider_market_mapping(provider,underlying_symbol,exchange).mapping_status=="SUPPORTED"
 except ValueError:return False
