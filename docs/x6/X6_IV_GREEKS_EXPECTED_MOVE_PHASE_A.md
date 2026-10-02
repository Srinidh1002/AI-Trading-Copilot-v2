# X6-A — IV, Greeks and Expected Move: model inputs and provenance

Branch baseline: `x23-shadow-features-v2`, frozen X5 commit `8c012ea689fc8abd323cd961069abcf037a27fa6`.

Scope: **offline, data-only Shadow research**, five canonical markets, no trading vote, contract selection, order submission, position/risk changes, dashboard decision authority, or PAPER certification counting. No source changes to Brain V1, X1–X5, or the R2.2 PAPER worktree.

- For NIFTY and SENSEX, Phase A declares `BLACK_SCHOLES_SPOT` with explicit verified spot, continuously compounded annual decimal risk-free rate, and annual decimal continuous dividend yield. Neither rate nor yield may be silently defaulted to zero.
- For CRUDEOILM, GOLDM and NATGASMINI, Phase A declares `BLACK_76_FUTURES` with a verified futures reference, underlying futures contract identity and expiry. Do **not** apply spot Black–Scholes with commodity spot substituted for the underlying futures contract.
- `option_expiry_at` is a separately sourced, timezone-aware *instant*. The date alone is insufficient. Time to expiry is ACT/365 using calendar seconds, not exchange-trading days; an expired option is unavailable for B1 pricing.
- Underlying price units follow X5: index points, INR/barrel, INR/10g, or INR/MMBTU. Premium is stated in the **same explicit market-native unit** as the verified X5 option premium and underlying reference (e.g. `INDEX_POINTS`, `INR_PER_BARREL`), per one underlying unit, never a lot-cost, per-contract P&L or execution quote. The caller must declare the unit and the context rejects an omitted or incorrect market-specific unit.
- Rates are continuous decimal/year (e.g. 0.06, not 6), bounded to [-1, 1]; implied-volatility outputs in subsequent phases will use decimal per sqrt(year). Greeks must declare units and conventions before use.
- The X6 capture binds to the **content SHA-256** of one immutable X5 capture, with exact session, as-of, expiry, option identity, option source-record ID and observed timestamp. Premiums must equal the named X5 LTP or bid/ask midpoint and may only be verified if the X5 premium has the matching verified unit. No independent provider call is performed.
- An independently supplied verification flag is a caller assertion, not independently demonstrated FYERS semantics. The Phase A validator checks consistency and hash binding, not market-data truth; live-source verification remains outstanding.
- A partial strike window can be represented with a warning. Retrospective observations cannot claim contemporaneous availability. Incomplete pricing assumptions produce explicit unavailable states, not guessed values.

Next: X6-B1 independently tested Black–Scholes spot and Black-76 futures reference mathematics, put/call parity, near-zero-time behavior, discounting, strict model applicability and premium bounds. X6-B2 implements IV solvers and dimensional Greeks; X6-B3 implements historical IV regime and expected move. Only X9 registers Shadow V2 features, and X10 may evaluate them read-only.
