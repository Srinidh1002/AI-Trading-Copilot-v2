# P4-1 canonical paper execution contracts

## Scope

P4-1 creates immutable deterministic contracts only. It does not implement an executor, route runtime traffic, invoke legacy execution, contact a broker or provider, or write a database/filesystem. Every contract fixes `execution_mode` to `PAPER` and `live_execution_eligible` to `False`.

## Contracts created

| Contract | Purpose | Primary linkage |
| --- | --- | --- |
| `PaperExecutionRequestV1` | Future executor instruction; not authorization itself. | Authorization ID, idempotency key, complete canonical/candidate identity, sized values and validity. |
| `PaperExecutionResultV1` | Immutable result of one execution attempt. | Request/idempotency plus bounded authorization, candidate, risk, plan, sizing, identity, quantities, prices and timing. |
| `PaperOrderStateV1` | Immutable record for a future in-memory lifecycle. | Order/request/idempotency plus authorization/result/candidate/risk linkage and reasons. |

Serialization is deterministic primitive-only dictionaries/JSON: timezone datetimes and dates are ISO-8601 strings, collections are lists, and JSON keys are sorted. No contract accepts nested request/candidate/risk objects, credentials, broker payloads, or mutable metadata.

## Controlled vocabularies and invariants

- Request: `PAPER`; `BUY/CALL/LONG` or `SELL/PUT/LONG` only.
- Result: `ACCEPTED`, `FILLED`, `REJECTED`, `BLOCKED`, `DUPLICATE`, `FAILED`.
- State: `CREATED`, `AUTHORIZED`, `SUBMITTED`, `FILLED`, `REJECTED`, `BLOCKED`, `CANCELLED`, `FAILED`.
- Underlying identity is NIFTY/NSE or SENSEX/BSE only. Short premium, live mode, live eligibility, broker order ID, and credential fields are not representable.

The request requires non-empty IDs/idempotency key, complete linkage, positive sized/risk values, `quantity == lots * lot_size`, valid expiry, `valid_until > valid_from`, and long-premium stop/target geometry.

`FILLED` results require complete identity, submitted/filled ordering, positive requested/filled quantities/lots/prices/capital/loss, no blockers, and filled values no greater than requested. `ACCEPTED` requires complete request linkage and submission time with no fill data. `REJECTED`, `BLOCKED`, and `FAILED` require blockers; `DUPLICATE` requires a blocker or warning; non-filled results prohibit fabricated fill data.

`CREATED` has no fill data. `AUTHORIZED` requires authorization. `SUBMITTED` requires authorization and complete actionable long-premium identity/values. `FILLED` additionally requires a result ID and fill price. `REJECTED`, `BLOCKED`, and `FAILED` require blockers; `CANCELLED` requires a reason and cannot carry a fill price.

## Identity, idempotency, and lifecycle

The request links snapshot, analysis, decision, trade-plan result, trade plan, sizing result, canonical risk result, candidate, and authorization by ID. The idempotency key is an explicit immutable input, not generated or consumed in P4-1. P4-2 will bind authorization; P4-3/P4-5 will enforce exactly once behavior in isolated in-memory components.

| Current | Allowed next |
| --- | --- |
| `CREATED` | `AUTHORIZED`, `BLOCKED`, `FAILED` |
| `AUTHORIZED` | `SUBMITTED`, `BLOCKED`, `FAILED` |
| `SUBMITTED` | `FILLED`, `REJECTED`, `CANCELLED`, `FAILED` |
| `FILLED`, `REJECTED`, `BLOCKED`, `CANCELLED`, `FAILED` | None (terminal) |

`PaperOrderStateV1.can_transition_to()` is pure and deterministic; it neither stores state nor performs a transition.

## Explicit safety exclusions

No executor, routing, candidate-preparation change, authorization runtime, broker/provider/Angel import, network call, database/filesystem write, legacy `execute_paper_trade` call, automatic approval, live execution, margin, short options, fees, tax, brokerage, slippage, or capital fetching was added.

## Manual test commands

```powershell
venv\Scripts\python.exe -m pytest tests/test_paper_execution_request_v1.py -q
venv\Scripts\python.exe -m pytest tests/test_paper_execution_result_v1.py -q
venv\Scripts\python.exe -m pytest tests/test_paper_order_state_v1.py -q
venv\Scripts\python.exe -m pytest tests/test_paper_execution_request_v1.py tests/test_paper_execution_result_v1.py tests/test_paper_order_state_v1.py -q
```

## Certification checklist

- [ ] User runs focused contract, P4, canonical, paper, safety, and full-repository gates.
- [ ] User performs the import check.
- [ ] P4-1 remains uncertified until manual gates pass.
- [x] No execution path was enabled by P4-1.
