# Provider-neutral data quality and freshness

P5-2 adds immutable provenance, quote, candle, series, freshness-policy, and
quality-result contracts. Pure evaluators classify VALID, warnings, stale,
future, empty, malformed, incomplete, and conflicting evidence without calls,
caches, sessions, resampling, or provider migration. The initial policy is a
bounded `INITIAL_CANONICAL_POLICY`, not a provider SLA. Quote/candle timestamps
are timezone-aware; cache evidence is caller-supplied provenance. Consensus
uses median-relative basis points and never selects or replaces a provider.
All four canonical identities are supported. P5-3 multi-timeframe intelligence
is next; P3/P4 semantics remain unchanged.
