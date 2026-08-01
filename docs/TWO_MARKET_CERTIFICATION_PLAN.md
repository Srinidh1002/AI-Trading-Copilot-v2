# Two-Market PAPER Certification Plan

## Current boundary

NIFTY/NSE and SENSEX/BSE have fixed certified provider identities. The runtime
currently evaluates one configured primary market per cycle. This plan is a
future certification gate for the missing two-market coordinator; it is not a
claim that cross-market ranking is live today.

## Per-market trade target

Certify **100 PAPER trades for NIFTY** and **100 PAPER trades for SENSEX**.
Each market’s 100 must contain:

- 60 deterministic replay trades, covering ready, no-trade, stale, unavailable,
  blocked, duplicate, recovery, partial exit, target exit, and stop exit paths.
- 40 live-session PAPER trades, with retained runtime/journal/P7/P8 evidence.

No-trade is a valid analytical outcome and must be counted separately from an
executed PAPER trade; it does not fill the 100-trade target. It is nevertheless
required evidence that entry gates remain selective.

## Required Phase C certification gates

1. One parent cycle creates exactly one NIFTY and one SENSEX child evaluation.
2. Child observation timestamps meet an explicit skew/freshness policy.
3. One provider failure preserves the other child result.
4. A dedicated two-market ranker evaluates both candidates, selects at most one
   eligible market, and preserves score, blockers, warnings, and rejection
   rationale for both.
5. Only the selected eligible result reaches P6/P7/P8; all-ineligible cycles
   are no-action with retained two-market evidence.
6. Active-position monitoring and restart recovery discover persisted P7/P8
   state for both market identities.
7. All outputs remain `PAPER`, `live_execution_eligible=false`, and
   `broker_order_submission=false`.

## Evidence needed before certification

- Exact-once per-market call counts and deterministic replay hashes.
- Pair-level rank/selection records, including losing-market reasons.
- A 30-cycle clean outer soak plus inner-result review for both markets.
- Reviewed provider rate-limit, timeout, stale, unavailable, and restart cases.
- The per-market 60 replay + 40 live-session trade evidence described above.

Until these gates exist, run NIFTY and SENSEX only as separate single-market
observations and do not market the runtime as a two-market selector.
