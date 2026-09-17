# Small-Capital Live Safety Policy

## Status

This policy defines future prerequisites only. It does not authorize live
trading and cannot change the certified runtime’s `PAPER` execution mode,
`live_execution_eligible=false`, or `broker_order_submission=false`.

## Strict prerequisites before any live proposal

1. Complete the NIFTY and SENSEX PAPER certification targets in
   `TWO_MARKET_CERTIFICATION_PLAN.md`, including reviewed replay and live-
   session evidence.
2. Implement and certify true two-market collection, ranking, selection, active
   position monitoring, and restart recovery. Separate-market observations are
   insufficient.
3. Demonstrate no unresolved broker rate-limit, timeout, stale-data, duplicate,
   persistence, or recovery defects across the approved soak window.
4. Require explicit human approval for every live session and every live order;
   no autonomous promotion from PAPER is permitted.
5. Use a separately reviewed live-execution design with independent order
   submission gates, position reconciliation, kill switch, loss limits,
   capital reserve, and incident response. None is enabled by this document.
6. Establish a small-capital limit that can be lost without financial harm,
   enforce one position at a time initially, and require a hard daily loss cap
   and immediate manual stop authority.

## Non-negotiable operational rules

- A no-trade decision is correct when evidence is insufficient.
- No process exit code, outer completion counter, or backtest alone authorizes
  live execution.
- Rate-limit exhaustion, missing/corrupt persistence, unexpected inner failure,
  or missing reconciliation is an immediate no-trade and review condition.
- Do not modify `config` or runtime safety flags to bypass these prerequisites.

Any future live proposal requires a separately approved change and certification
record. This repository checkpoint remains PAPER-only.
