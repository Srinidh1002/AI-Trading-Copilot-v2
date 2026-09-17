# P4-3A4 four-index replay and certification

## Certification decision

**Certified.** NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE support
deterministic BUY/CALL/LONG and SELL/PUT/LONG flow through identity, contracts,
authorization, deterministic execution, and duplicate prevention.

## Files and scenarios

Created `tests/test_replay_four_index_end_to_end.py` (48 cases) and
`tests/test_four_index_identity_regression.py` (40 cases). Replay covers every
actionable direction, authorized full fill, live-ineligible result, and duplicate
without second fill. Regression covers exact registry order, valid pairs,
mismatches, unsupported symbols, aliases, and deterministic normalization.
No runtime compatibility defect was found in this certification pass.

## Executed results

| Gate | Result |
| --- | --- |
| Replay focused | 48 passed |
| Identity regression | 40 passed |
| Combined P4-3A4 | 88 passed in 0.80s |
| P4-3A focused compatibility | 516 passed in 1.45s |
| P3 regression | 632 passed in 1.67s |
| P4 regression | 457 passed in 1.22s |
| Canonical regression | 275 passed in 1.21s |
| Paper/safety regression | 241 passed in 1.86s |
| Full repository | 4,667 passed in 14.96s |

Import check output:
```text
(('NIFTY', 'NSE'), ('BANKNIFTY', 'NSE'), ('FINNIFTY', 'NSE'), ('SENSEX', 'BSE'))
P4-3A imports passed
```

The full suite and paper/safety subgroup showed only the two existing SmartAPI
TLS deprecation warnings (`ssl.OP_NO_TLSv1` and `ssl.OP_NO_TLSv1_1`).

## Safety confirmation

No sizing/risk/executor formulas, scoring, authorization semantics, idempotency
semantics, persistence, broker/provider/network/filesystem behavior, paper
automation, live execution, short options, fees, taxes, brokerage, margin,
spread, or slippage were added. P4-4 remains the next phase.
