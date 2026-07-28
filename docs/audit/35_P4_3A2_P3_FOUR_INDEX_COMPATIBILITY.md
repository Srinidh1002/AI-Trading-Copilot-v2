# P4-3A2 P3 four-index compatibility

P3 option-contract, universe, selected-contract, trade-plan, position-size, and
position-sizing identity gates now consume `SUPPORTED_MARKET_IDENTITIES` from
`services.core.market_identity`. This admits NIFTY/NSE, BANKNIFTY/NSE,
FINNIFTY/NSE, and SENSEX/BSE while retaining canonical exact-value contract
validation and rejecting mismatched pairs.

The registry is imported directly from `services.core.market_identity`; its
lazy core package snapshot wrapper prevents eager options/contracts import
cycles. No P4 request/authorization/result/order/executor file was changed.
Lot size remains an explicit option/plan fixture or provider-derived input; no
static live lot size was added. Existing session identity normalization now
accepts the new NSE symbols, while P4-3A3 must expand P4 identity contracts.

| Area | Four-index behavior |
| --- | --- |
| Option contracts/universe/selection input | Exact pair accepted; mismatches rejected. |
| Trade plan/risk sizing | Exact pair preserved; formulas and execution false unchanged. |
| Session identity | New NSE identities normalize; exchange mismatch rejects. |
| Paper candidate/execution | P3 candidate compatibility fixtures added; P4 execution remains intentionally unexpanded. |

New focused suites: option contracts 30, option selection 30, trade plan 30,
risk 35, paper candidate 25, session 25; total 175.

Manual commands:
```powershell
venv\Scripts\python.exe -m pytest tests/test_four_index_option_contract_compatibility.py tests/test_four_index_option_selection.py tests/test_four_index_trade_plan_compatibility.py tests/test_four_index_risk_compatibility.py tests/test_four_index_paper_candidate_compatibility.py tests/test_four_index_session_compatibility.py -q
venv\Scripts\python.exe -c "from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES; print(SUPPORTED_MARKET_IDENTITIES)"
```

P4-3A2 is implemented but uncertified. Safety: no formula, scoring, lot-size
ownership, authorization, executor, broker/provider, persistence, or automatic
execution change was made.
