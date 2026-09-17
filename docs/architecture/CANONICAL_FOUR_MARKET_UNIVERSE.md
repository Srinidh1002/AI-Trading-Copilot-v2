# Canonical four-market universe

P5-1 defines the static provider-neutral Phase-One universe: NIFTY/NSE,
BANKNIFTY/NSE, FINNIFTY/NSE, SENSEX/BSE, in that order. `MarketInstrumentV1`
holds immutable display metadata, aliases, position, INR, Asia/Kolkata, and
INDEX controls. `MarketUniverseV1` contains the exact paper-only ordered tuple.

Outer boundaries normalize only certified aliases. Immutable contracts accept
only canonical identity pairs. Runtime APIs provide deterministic lookup/list/
identity resolution with no fallback, inference, network, environment, client,
or provider behavior.

`ProviderMarketMappingV1` makes provider evidence observable. The only proven
static mapping is NSE_OPTION_CHAIN NIFTY/NSE → `NIFTY`/`NSE`; YFINANCE and
ANGEL_SMARTAPI mappings, and other NSE chain identities, remain UNKNOWN rather
than guessed. Reverse lookup fails closed.

This module excludes lot sizes, expiries, strikes, tokens, authentication,
prices, option contracts, freshness, quality, and MTF data. P3/P4 identity APIs
remain unchanged. Legacy yfinance, Angel, NSE, and duplicate registry paths are
retained for compatibility but are `DO_NOT_USE_FOR_NEW_CODE` until later P5
adapter phases. P5-2 adds quality/freshness without changing execution.
