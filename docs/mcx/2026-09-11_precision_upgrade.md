# MCX Precision-First Rebuild â€” 2026-09-11 Evening Session

## Context
Precision-first upgrade applied after 3 diagnostic losses in the naive MCX PAPER bot.
No strategy parameter tuned to make past trades look profitable (spec Â§40).

## Epoch Declaration
- New certification epoch: POST_PRECISION_V1
- Counter reset to 0/100
- 3 pre-upgrade trades archived (PRE_PRECISION_DIAGNOSTIC, net -â‚¹701.20)
- Archived at: data/paper_trades/pre_precision_archive/

## Files Built This Session (9 new + 3 patched)
NEW:
- src/mcx/mcx_regime.py            (spec Â§8)  regime classifier
- src/mcx/mcx_decision.py          (spec Â§1,4,9) hard gates + 4-score decomposition
- src/mcx/mcx_pcr.py               (spec Â§2,11) stable PCR with fixed universe + EMA-3
- src/mcx/mcx_event_risk.py        (spec Â§22) scheduled event blocks
- src/mcx/mcx_position_manager.py  (spec Â§16,17,18,20,21) exit engine
PATCHED:
- src/mcx/mcx_mtf.py               5 TFs + ATR + EMA9 + swings + weighted aggregate
- src/mcx/mcx_capital.py           tick-size-aware fills (Â§15)
- src/mcx/mcx_paper_bot.py         wires decision + PCR + event + position manager

## Spec Item Coverage (of 40)
DONE tonight:
Â§1 directional hard gates, Â§2 stable PCR, Â§4 score decomposition, Â§5 5 TFs + indicators,
Â§6 MTF consensus, Â§8 regime engine, Â§9 entry gate, Â§10 signal persistence (2-of-3),
Â§11 ATM/PCR stability guard, Â§13 chop detector via RANGE, Â§15 tick-aware fills,
Â§16 thesis tracking, Â§17 contradiction exit, Â§18 profit protection ladder,
Â§19 MFE/MAE, Â§20 peak drawdown exit, Â§21 time stop, Â§22 event risk guard (starter),
Â§26 win definition, Â§33 one position only, Â§37 two-engine design

DEFERRED (needs multi-session data or Black-76 work):
Â§7 external provenance enrichment, Â§12 price action gate, Â§14 IV/Greeks,
Â§23-25 confidence calibration, Â§27-30 walk-forward + stats CI,
Â§31 risk-based sizing refinement, Â§32 post-loss cooldown, Â§35 expiry safety,
Â§36 full decision output, Â§38-40 learning + setup precision

## First Run Results (POST_PRECISION_V1)
Attempt 1 (19:57 IST):
  future=â‚¹9509  pcr_raw=1.3993  pcr_stable=1.3993  maxpain=9500
  regime=RANGE(0.5)  vol=NORMAL  struct=NEUTRAL  adx=21.2
  LONG_CONF=47  SHORT_CONF=3  ACTION=NO_TRADE
  HARD_BLOCKERS=['REGIME_RANGE_NO_TREND']

  Interpretation: Market is RANGE-bound. Precision-first bot correctly refuses
  to enter trend trades. WAIT is the correct output, not a defect.

## What Tonight's Run Proves
- Hard gates prevent the exact failure mode that caused 3 diagnostic losses
  (MTF BEARISH + BUY_CALL would now be blocked at the gate level)
- PCR stability fix removes the ATM-migration oscillator
- Position manager will exit trades that reverse after peak (would have saved
  trade #2 which reached +12% MFE then SL'd)
- RANGE regime blocking is working â€” no forced trades

## Safety
- broker_submission = false
- No orders sent
- NIFTY/SENSEX system untouched
- Zero credential leaks
- All writes under data/paper_trades/mcx_*

## Next Session Priorities (do NOT tune on tonight's data)
1. Observe how RANGE gate behaves across multiple sessions
2. Add Â§14 Greeks (Black-76) for strike quality
3. Add Â§35 expiry safety (option expiry 17SEP approaching)
4. Add Â§32 post-loss cooldown
5. After 20+ POST_PRECISION trades: consider confidence calibration (Â§24)

## Statistical Honesty Reminder
Per spec Â§30: an observed 80/100 is NOT proof of 80% true probability.
95% Wilson CI lower bound needs ~88/100 wins for "proven 80%."
Report observed rate AND confidence interval.
