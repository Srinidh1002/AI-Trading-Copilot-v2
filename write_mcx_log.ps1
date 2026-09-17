$log = @"
# MCX PAPER Trading Session — 2026-09-11 (Evening)

## Context
First live MCX PAPER session. CRUDEOILM only. Read-only + PAPER only.
No live broker orders. NIFTY/SENSEX untouched.

## Outcome (attempt 138, still running)
- Trades closed: 2 (both STOP_LOSS)
- Trade 3: OPEN, +3.63% at last check
- Total P&L (closed): -₹1,524.08
- Progress: 2/100 closed

## Trade 1 — MCX_20260911_170803
- CE 9500, entry=₹366.49, exit=₹331.39
- Gross=-₹702.00, Costs=₹84.01, NET=-₹786.01 (-10.72%)
- Exit: STOP_LOSS
- Entry context: bias=BULLISH MOD, MTF=MIXED, ext=UP
- MFE/MAE not tracked in this run (should be added)

## Trade 2 — MCX_20260911_171940
- CE 9500, entry=₹335.67, exit=₹302.95
- Gross=-₹654.40, Costs=₹83.67, NET=-₹738.07 (-10.99%)
- Exit: STOP_LOSS
- Entry context: bias=BULLISH MOD, MTF=BEARISH, ext=UP
- Held ~65 minutes with MFE +12% then reversed to SL

## Trade 3 — MCX_20260911_183449 (OPEN at time of log)
- CE 9500, entry=₹302.00
- SL=₹277.84, T1=₹347.30
- Last check: ltp=₹312.95, pnl=+3.63%

## Known Issues Discovered (NOT FIXED — needs multi-session evidence)
1. **Bias over-weights contrarian PCR vs directional MTF**
   - All 3 entries were CE while MTF was BEARISH/MIXED
   - Composite: bull(1.7) from chain+external beat bear(1.0) from MTF
   - Same failure mode as NIFTY/SENSEX Friday session
   - RULE 17: needs 30+ trades to validate before change

2. **PCR instability from chain window**
   - PCR oscillates 1.20–1.50 as ATM crosses large OI strikes
   - When ATM=9450, window includes 9400 PE wall (404K OI) -> PCR spikes
   - When ATM=9500, same wall is outside window -> PCR drops
   - Fix would require asymmetric window or OI-normalized metric
   - RULE 17: log now, fix after multi-session data

## What Works
- Full pipeline: identity -> chain -> external -> MTF -> bias -> strike -> fill -> lifecycle -> ledger
- No fabrication, no cross-market fallback, no orders
- Credentials never logged

## Next Session Priorities
1. Add MFE/MAE tracking to MCX paper bot (mirror NIFTY outcome_ledger)
2. Add trailing-stop option after T1 (Trade 2 hit +12% before SL)
3. Investigate bias weighting with 30+ trades before any change
4. MCX-05 (Black-76 IV/Greeks) for better strike selection
"@
$log | Out-File -FilePath "docs\mcx\2026-09-11_mcx_paper_session.md" -Encoding UTF8
Get-Item "docs\mcx\2026-09-11_mcx_paper_session.md" | Select-Object Name, Length
