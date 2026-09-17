# MCX Certification Criteria — POST_PRECISION_V2

Declared: 2026-09-11 22:00 IST
Rule locked. No strategy changes allowed during epoch.

## Countable Trade Definition

A trade is COUNTABLE only when ALL of these are true:

  - Executed on real market data (no replay, no synthetic)
  - Has a valid PAPER fill at realistic price (ask + slippage, tick-aligned)
  - Has a monitored position lifecycle (entry_time, monitor cycles, exit_time)
  - Exited via a defined exit_reason (T1 / T2 / T3 / STOP_LOSS / CONTRADICTION /
    THESIS_INVALIDATED / TRAILING_STOP / PEAK_DRAWDOWN / TIME_STOP /
    EVENT_EXIT / SESSION_EXIT / MCX_CLOSE_2310 / DATA_FAILURE_SAFETY)
  - Reconciled (gross P&L, costs, net P&L all computed)
  - Not duplicate trade_id
  - Epoch = POST_PRECISION_V2, strategy_version = MCX_POST_PRECISION_V2

## Win / Loss Definition

  WIN  = T1 (entry × 1.15) reached BEFORE SL (entry × 0.92) is reached
  LOSS = SL reached BEFORE T1

  Note: T2/T3 exits count as wins (T1 was necessarily crossed en route,
  unless gap-skipped; if gap-skipped through T1 to T2 exit, still counts
  as win — T1 was crossed in real market data).

  Contra-exit / thesis-invalidated / peak-drawdown / time-stop exits that
  close in net positive territory are WINS.
  Same exits closing in net negative territory are LOSSES.
  This keeps the criterion outcome-based (net positive/negative at close),
  measured against the fixed T1/SL thresholds.

## Pass Requirement

  T1_HIT_WINS >= 80 out of 100 countable trades

  79/100 or fewer → FAIL, do NOT certify, move to V3 development
  80/100 or more  → PASS candidate, then run diversity check (below)

## Diversity Check (secondary gate, applied after 80% pass)

  - Trades across >= 5 distinct trading days
  - Trades across >= 2 regimes (e.g. TREND_UP + BREAKOUT_UP)
  - Trades across >= 2 session phases (morning + evening for MCX)
  - No single day contributing > 40 countable trades

  If diversity check fails, do not certify — expand the epoch across more
  sessions and re-evaluate.

## Secondary Metrics (report, do NOT gate)

  - Net P&L per trade and cumulative
  - Profit factor (gross gains / gross losses)
  - Maximum drawdown
  - Expectancy per trade
  - MFE / MAE distribution
  - Profit giveback distribution
  - Cost ratio (costs / gross P&L)
  - Session-of-day win rate
  - Regime-specific win rate
  - Setup-specific win rate
  - Confidence calibration (does 80% confidence actually win 80%?)

  These are diagnostic. They do not count toward pass/fail, but they
  will determine whether we trust an 80% result.

## Learning Rule

  The bot MAY collect every feature and outcome during the epoch.

  The bot MUST NOT modify thresholds, weights, gates, or any strategy
  logic during the epoch.

  Any proposed change requires:
    1. Epoch complete (100 trades or explicit abort)
    2. Offline analysis
    3. Walk-forward / replay validation
    4. Version bump (POST_PRECISION_V3)
    5. Fresh epoch, reset counter to 0

## Exclusions from Denominator

  WAIT, NO_TRADE, open positions, unreconciled trades, replays,
  synthetic trades, duplicates, and any trade whose
  certification_eligible flag is false.

## Reference

Handoff V3.0 PART 4, PART 6, PART 11 (RULE 19, RULE 20)
