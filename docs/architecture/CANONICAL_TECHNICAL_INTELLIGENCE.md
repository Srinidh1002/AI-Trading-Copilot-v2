# Canonical technical intelligence

P5-4 is a paper-only, provider-neutral technical-evidence pillar for NIFTY/NSE,
BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE in 5m, 15m, 1h, and 1d order.
It produces bounded technical evidence, not decisions.

## Contracts, APIs, and policy

Immutable contracts are `TechnicalIndicatorValueV1`,
`TimeframeTechnicalEvidenceV1`, `TechnicalIntelligenceResultV1`, and
`TechnicalIntelligencePolicyV1`. Public APIs include pure indicator primitives,
five category evaluators, timeframe analysis, aggregation, and the canonical
pipeline. The default policy is `INITIAL_CANONICAL_TECHNICAL_POLICY`.

Timeframe weights are 5m=.35, 15m=.30, 1h=.20, 1d=.15. Category weights are
trend=.25, momentum=.20, volatility=.15, volume=.15, levels=.15, patterns=.10.
Incomplete and insufficient history BLOCK; conflicting timeframes WARN. These
are initial architectural values, not statistically calibrated weights.

## Formulas and evidence

SMA is arithmetic mean; EMA is SMA-seeded. RSI, ATR, and ADX use Wilder
initialization/smoothing. MACD aligns its signal EMA to the complete fast/slow
sequence. True range includes previous close. Bollinger Bands use population
standard deviation; VWAP uses typical-price volume weighting. RSI=14, EMA=20/50,
MACD=12/26/9, ADX=14, ATR=14, Bollinger=20/2.0, volume/levels=20, RSI=70/30,
ADX=25.

Only completed candles are evaluated: no sorting, interpolation, forward fill,
resampling, synthetic candles, or look-ahead. Trend uses EMA/ADX; momentum uses
RSI/MACD; volatility uses ATR and Bollinger width; volume derives solely from
volatility evidence; levels exclude the evaluated candle; patterns have fixed
engulfing, hammer/shooting-star, doji, inside-bar, outside-bar precedence.

## Aggregation and safety

Trend, momentum, above/below levels, and bullish/bearish patterns contribute
signed score. Volatility and volume cannot create direction. Unavailable weight
stays unearned—there is no renormalization. Timeframe thresholds are +/-0.10
and aggregate thresholds +/-0.15. Aggregate strength is bounded signed-score
magnitude, never probability or confidence. Material opposition is MIXED.

P5-3 supplied quality is authoritative and stale/future/malformed/unsupported/
failed/missing or policy-blocked evidence fails closed. No P5-2/P5-3 rebuild is
performed. The pillar contains no provider, network, cache, environment,
BUY/SELL/HOLD/WAIT, regime, option, ranking, risk, or execution behavior.
Legacy technical paths remain compatibility-only. P5-5 option-chain intelligence
is the next handoff.
