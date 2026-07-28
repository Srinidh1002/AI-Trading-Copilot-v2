# PaperTradeCandidate v1

`PaperTradeCandidateV1` is a frozen, deterministic, side-effect-free
preparation artifact. It is not an order and cannot write paper-trade state.

It requires matching snapshot/decision identifiers, a directional action,
explicit CE/PE option type, a tradingsymbol or instrument token, positive
entry/stop/quantity, one or more valid strictly increasing targets, timezone-aware creation and
expiry timestamps, and an internally consistent stop direction. It never
infers an instrument, option type, plan field, or quantity.

A single target is preserved as a single target; the contract never derives or
duplicates another target. BUY long-option candidates require targets above the
entry price.

`position_side` distinguishes premium position semantics from decision action.
It defaults to `LONG` for legacy BUY candidates and `SHORT` for legacy SELL
candidates. A SELL/PE candidate may explicitly be `LONG`, using long-premium
stop and target rules without altering legacy short SELL behavior.

`prepare_paper_candidate` is validation-only. Current canonical decisions are
`ANALYSIS_ONLY` and plan-free, so they normally return `NEEDS_TRADE_PLAN` with
no candidate. `execute_paper_candidate` is the only submission boundary; it
requires explicit approval, a fresh matching candidate, `PAPER_READY`,
`NOT_REQUESTED`, fresh data health, and invokes only the legacy paper executor.
It never invokes a live broker.
