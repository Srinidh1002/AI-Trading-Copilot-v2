# Canonical multi-timeframe intelligence

P5-3 consumes supplied P5-2 candle series only. It creates immutable
timeframe evidence, ordered snapshots, and quality results for 5m, 15m, 1h,
and 1d, anchored on 5m. The initial policy requires 60/60/50/50 completed
candles and has explicit alignment tolerances. No fetch, cache, resampling,
indicator, session calendar, provider migration, scoring, decision, or
execution behavior is present. P5-4 technical intelligence is next.
