# P5-1 canonical four-market universe audit

## Decision

P5-1 is certified. Existing `services/core/market_identity.py` was reviewed
and intentionally retained unchanged to preserve P3/P4 API behavior.

## Universe and aliases

| Position | Canonical | Display | Outer-boundary aliases |
|---|---|---|---|
| 1 | NIFTY/NSE | NIFTY 50 | NIFTY, NIFTY50, NIFTY 50 |
| 2 | BANKNIFTY/NSE | NIFTY BANK | BANKNIFTY, BANK NIFTY, NIFTY BANK |
| 3 | FINNIFTY/NSE | NIFTY FINANCIAL SERVICES | FINNIFTY, FIN NIFTY, NIFTY FINANCIAL SERVICES |
| 4 | SENSEX/BSE | BSE SENSEX | SENSEX, BSE SENSEX |

Contracts are immutable and primitive-serializable; all are INDEX/INR/
Asia/Kolkata/enabled and contain no price, lot, expiry, strike, token, or live
provider data.

## Provider evidence

`services/option_chain_live.py` proves only NSE_OPTION_CHAIN NIFTY → NIFTY/NSE
(AUTHORITATIVE_EXISTING). YFINANCE and ANGEL_SMARTAPI use dynamic symbols or
tokens and expose no safe static identity mapping (UNKNOWN). BANKNIFTY,
FINNIFTY, and SENSEX provider symbols are never guessed. Duplicate paths in
`market_data.py`, broker/market registries, and option modules are retained
compatibility/legacy and `DO_NOT_USE_FOR_NEW_CODE` pending P5-2/P5-5.

## APIs and isolation

`market_universe` exports canonical constants and bounded lookup/alias APIs.
`provider_market_adapter` exports list/get/resolve/reverse/support APIs. Neither
imports providers, clients, analysis, execution, repositories, filesystem, or
network modules.

## Certification evidence

Focused: market instrument `52 passed in 0.64s`; universe `45 passed in
0.68s`; canonical universe `78 passed in 0.69s`; provider adapter `75 passed
in 0.69s`; identity compatibility `52 passed in 0.66s`; isolation `35 passed
in 0.62s`; combined `337 passed in 1.09s`.

Existing identity regression: `178 passed in 0.80s`; P3 compatibility: `175
passed in 0.96s`; P4 compatibility: `275 passed in 1.06s`; P4 boundary: `138
passed in 0.73s`; P5-0 invariants: `35 passed in 0.64s`. Import output lists
the identical four-pair canonical and legacy tuples, `12` static mappings, and
`P5-1 imports passed`; isolation output is `[]` and `P5-1 isolation imports
passed`. Full suite: `6381 passed, 2 warnings in 17.36s`.

One newly-added isolation test was corrected: it had treated provider modules
loaded by unrelated tests as imports made by P5-1. The corrected test examines
only P5-1 module namespaces. No runtime defect was found. The two warnings are
the pre-existing SmartAPI TLS deprecations. Runtime diff: only P5-1 static core
contracts/adapters, exports, tests, and documentation were added; no provider,
data, intelligence, P3/P4, or dashboard module was changed by P5-1. P5-2
quality/freshness is next.
