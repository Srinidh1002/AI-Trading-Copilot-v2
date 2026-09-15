# Task 9 production authority map

| Fact | Writer / authority | Reader | Notes |
|---|---|---|---|
| Official run identity | launcher manifest | launcher/runtime | Bound to `official_run_id`; atomic JSON. |
| Historical request | `LiveMultiTimeframeData` | Task 8 capture | Cache → cooldown → gate → provider. |
| Provider quota blocker | blocker store + incident ledger | launcher/dashboard read model | Runtime incidents only from typed handoff. |
| Parent decision/predictions | authoritative two-market parent + ledger | Task 8 / Task 9 | Exact two-market evidence. |
| Task 9 cycle receipt | `Task9LivePaperCycleResultStore` | recovery/reporting | Persisted before dashboard callback. |
| Entry/lifecycle/outcome/reconciliation | Task 8/Task 9 PAPER runtimes | counting evaluator | PAPER-only contracts. |
| `/100` decision | Task 9 counting evaluator | progress builder/reporting | Terminal reconciled actual PAPER entry only. |
| Dashboard snapshot | dashboard publisher/store | dashboard | Read-only; cannot count or trade. |

Secondary/compatibility authorities requiring care: legacy trading engine/order
manager, completed-candle compatibility API, old `market_data.py`, Task 6/Task 8
canary CLIs, and diagnostics capture modules. None is the active Task 9
authority.

R3 closure: `CompletedCandleService` shares the canonical durable historical
cooldown and request-gate state before its compatibility request. It is not
constructed by certified `capture_option_inputs`.

R4 closure: `services.market_data`/yfinance and `dashboard/home.py` are legacy
research compatibility. The authoritative Task 9 dashboard is
`app.py -> dashboard.dashboard_v2.home`, with publication/read-model inputs
only. No certification authority has an Angel-to-yfinance fallback.
