# P8D0 F7 — FYERS Data Provider Implementation Design

## Status

Implementation design frozen after P8D0 F3–F6 capability proof.

## Provider policy

- FYERS = PRIMARY market-data provider.
- ANGEL_SMARTAPI = SHADOW comparison provider.
- Both providers are DATA ONLY.
- Order capability is prohibited.
- Automatic fallback is prohibited.
- Provider failure must fail closed.
- Existing PAPER certification rules remain unchanged.

## Five-market universe

- NIFTY
- SENSEX
- CRUDEOILM
- GOLDM
- NATGASMINI

## Proven FYERS capabilities

### Instrument / futures resolution

NIFTY:
- underlying argument to futures_chain
- NSE:NIFTY50-INDEX

SENSEX:
- underlying argument to futures_chain
- BSE:SENSEX-INDEX

MCX:
- bare commodity root is not accepted by futures_chain
- current exact front FUT contract must first be resolved from FYERS symbol master
- exact front FUT is then supplied to futures_chain

### Quotes

FYERS quotes() is proven live.

Observed fields include:

- lp
- bid
- ask
- volume
- fyToken
- symbol
- timestamp-related fields

### Depth

FYERS depth() is proven live.

Observed fields include:

- ltp
- bids
- ask
- oi
- volume
- OHLC
- expiry
- tick size
- total buy quantity
- total sell quantity

### Historical candles

FYERS history() is proven live.

Standard candles:
- width 6

With oi_flag=1:
- width 7
- appended numeric non-negative OI

### Option chain

FYERS optionchain() is proven live.

Observed option fields include:

- symbol
- strike_price
- option_type
- ltp
- oi
- oich
- prev_oi
- volume
- bid
- ask
- fyToken
- expiry

### Futures chain

Proven for:

- NIFTY
- SENSEX
- CRUDEOILM
- GOLDM
- NATGASMINI

### Streaming

FYERS WebSocket transport/auth/subscription/live-tick capability is proven.

Existing trading runtime expects normalized ticks:

- token
- ltp
- ts

## Existing active runtime

run_nifty.py and run_sensex.py instantiate UnifiedTradingBot.

UnifiedTradingBot currently binds directly to Angel SmartAPI.

Direct Angel-shaped market-data methods in active path:

- ltpData
- getCandleData
- getMarketData("FULL")

Additional direct Angel dependencies exist in:

- MarketIntelligence
- EnhancedVIX
- OptionChainEngine
- PreviousDayEngine
- WebSocketFeed

## Existing V2 provider foundation

Reuse:

- InstrumentResolverV2
- HistoricalDataProviderV2
- QuoteDepthProviderV2
- StreamingMarketDataProviderV2
- ProviderRegistryV2
- ProviderRoutingPolicyV2
- SharedMarketDataHubV2
- SharedProviderOrchestratorV2
- ProviderRuntimeBundleV2
- ResolvedInstrumentV2
- MarketQuoteV2
- MarketDepthV2
- MarketCandleV2

The existing provider-foundation focused regression passed 42 tests.

## Migration strategy

The migration must be staged.

### Stage A

Create pure FYERS response normalization.

No SDK import.
No credentials.
No network.
No runtime wiring.
No broker execution.

### Stage B

Create FYERS data-only SDK adapter using the normalization layer.

Client must be injectable for unit tests.

### Stage C

Implement V2 provider protocols.

### Stage D

Create FYERS streaming normalization.

### Stage E

Introduce provider injection into UnifiedTradingBot.

Do not construct SmartConnect internally when FYERS runtime is selected.

### Stage F

Move subordinate engines away from Angel-shaped responses incrementally.

## Compatibility mappings

Angel ltpData:

    FYERS quotes
        ->
    compatibility normalization
        ->
    existing ltpData-shaped response

Angel getCandleData:

    FYERS history
        ->
    compatibility normalization
        ->
    existing candle response

Angel getMarketData FULL:

    FYERS quote/depth/optionchain
        ->
    compatibility normalization
        ->
    existing FULL quote/depth shape

Angel WebSocket:

    FYERS DataSocket
        ->
    normalize to:
        token
        ltp
        ts

## Non-actions

Do not:

- enable FYERS order APIs
- instantiate an order socket
- enable live execution
- alter PAPER certification counters
- change trading thresholds
- change capital rules
- change strategy logic
- change risk logic
- modify FYERS SDK
- globally disable IPv6
- automatically fail over to Angel
- remove Angel code yet
- rewrite the trading brain

## First implementation patch

The first source patch is limited to a pure FYERS response-normalization module and its unit tests.

It must not import:

- fyers_apiv3
- SmartApi
- requests
- urllib
- socket

It must not perform any I/O or network calls.
