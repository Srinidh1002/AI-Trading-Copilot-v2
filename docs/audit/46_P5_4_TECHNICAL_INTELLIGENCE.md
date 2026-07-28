# P5-4 technical-intelligence audit

P5-4 certifies immutable paper-only technical contracts, deterministic
standard-library indicators, category evidence, timeframe analysis,
non-renormalized aggregation, a supplied-evidence pipeline, four-index
compatibility, and clean-process import isolation.

| Policy area | Certified value |
|---|---|
| Markets | NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, SENSEX/BSE |
| Timeframes | 5m, 15m, 1h, 1d |
| Timeframe weights | .35, .30, .20, .15 |
| Category weights | .25, .20, .15, .15, .15, .10 |
| Quality controls | incomplete BLOCK; history BLOCK; conflict WARN |

EMA is SMA-seeded; RSI/ATR/ADX use Wilder smoothing; MACD is aligned;
Bollinger uses population deviation. Completed-candle/no-look-ahead protections
are mandatory. Scores preserve unearned unavailable weight. Aggregate strength
is not probability or final confidence.

Legacy technical modules—including technical analyzers, agents, candlestick and
chart-pattern engines, support/resistance implementations, and regime builders—
are RETAIN_COMPATIBILITY / DO_NOT_USE_FOR_NEW_P5_CODE pending a later adapter or
post-migration deprecation. P5-4 has no provider, fetch, cache, resampling,
option, regime, decision, ranking, risk, or execution behavior.

Corrected defects: ADX normalization, eager pandas contract import, volume
legacy-bias projection, MISALIGNED warning/blocker compatibility, and pipeline
clock validation order. Final gate output is recorded in the P5-4D handoff.
