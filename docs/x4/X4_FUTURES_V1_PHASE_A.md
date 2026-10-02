# X4 Futures Intelligence V1 — Phase A (pure calculation)

Status: offline candidate, **not frozen** and **not production-wired**.

## Scope

- Five markets: NIFTY, SENSEX, CRUDEOILM, GOLDM, NATGASMINI.
- Immutable explicit identity and verified contract-metadata requirement.
- Completed, quality-valid, strictly time-ordered samples from the same exact contract, session, timeframe, and historical as-of interval.
- Price change, verified OI delta/change, normalized OI acceleration, verified-volume change, and existing MCX-style price/OI positioning classes.
- **Candle typical-price VWAP approximation**, explicitly not genuine exchange/tick VWAP. No missing-volume substitution.
- Futures basis only against a separately verified, recent, market-matched, unit-matched benchmark. MCX requires actual verified commodity spot; no synthetic index/MCX spot.
- No independent directional vote for correlated OI metrics; X9/X10 must reduce them as one futures-positioning family.

## Integration responsibilities deferred to Phase B

- Explicit adapter from `ResolvedInstrumentV2` and FYERS provider/historical records, with exact provider timestamp semantics, OI unit confirmation, currency/quote-base unit confirmation and successful verification of contract metadata.
- Session-aware historical observation gathering via X1; no current quote masquerading as historical data; no forward-filled missing observations.
- Separate genuine VWAP calculation only if signed and verified price×volume/turnover data are available.
- Timeframe-specific freshness budgets and market-specific expiry cutoff via existing session authority.
- Feature manifest, research view, adversarial tests, scoped freeze, X1–X4 combined regression.

## Safety boundary

No import of any broker SDK, `src.mcx.mcx_paper_bot`, order APIs, execution, PAPER certification, environment variables or network access. No modification of existing X1–X3/B1–B4 code or R2.2 PAPER worktree. Do not stage or commit until local focused tests and security review pass.
