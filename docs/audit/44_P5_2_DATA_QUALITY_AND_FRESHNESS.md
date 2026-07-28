# P5-2 data quality and freshness audit

P5-2 is certified: provider-neutral contracts and pure evaluators add no
provider, cache, network, filesystem, environment, or execution behavior.
Legacy data paths remain retained compatibility and `DO_NOT_USE_FOR_NEW_P5_CODE`:
`market_data.py`, Angel live MTF, historical cache, and NSE/yfinance paths.

Default policy: quote/cache 300s, future/skew tolerance 5s, 1m–1d bounded
thresholds, incomplete WARN, empty BLOCK, disagreement warning/block 10/50bps.
Status severity is FAILED, UNSUPPORTED, MALFORMED, FUTURE, CONFLICTING, EMPTY,
STALE, INCOMPLETE, VALID_WITH_WARNINGS, VALID.

Combined P5-2: `642 passed in 1.46s`; combined P5-1/identity/P4 compatibility:
`653 passed in 1.67s`; import: `INITIAL_CANONICAL_POLICY`, `P5-2 imports
passed`; full suite: `7023 passed, 2 warnings in 18.52s`. The warnings are the
pre-existing SmartAPI TLS deprecations. One new candle test clock was corrected
to evaluate the completed candle at its end timestamp. P5-3 is next.
