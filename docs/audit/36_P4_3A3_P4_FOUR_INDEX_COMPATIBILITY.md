# P4-3A3 P4 four-index compatibility

P4 request, manual authorization, execution result, and authorization-result
contracts now use `SUPPORTED_MARKET_IDENTITIES` from the dependency-safe shared
registry module. The authorization validator and executor preserve exact
identity comparisons and therefore accept BANKNIFTY/NSE and FINNIFTY/NSE when
their validated request/authorization/session evidence agrees. No local
two-market executor gate existed; no idempotency change was required.

| Identity | BUY/CALL/LONG | SELL/PUT/LONG | Session-bound authorization | Full fill |
| --- | --- | --- | --- | --- |
| NIFTY/NSE | Yes | Yes | Yes | Yes |
| BANKNIFTY/NSE | Yes | Yes | Yes | Yes |
| FINNIFTY/NSE | Yes | Yes | Yes | Yes |
| SENSEX/BSE | Yes | Yes | Yes | Yes |

Focused suites: request 30, authorization 30, validator 35, execution result
30, order state 30, executor 40; total 195. Imports use
`services.core.market_identity` directly, avoiding eager core package graph
loading. No broker/provider, legacy executor, persistence, formula,
authorization-order, idempotency, or live-execution behavior changed.

Manual command:
```powershell
venv\Scripts\python.exe -m pytest tests/test_four_index_execution_request_compatibility.py tests/test_four_index_authorization_compatibility.py tests/test_four_index_authorization_validator.py tests/test_four_index_execution_result_compatibility.py tests/test_four_index_order_state_compatibility.py tests/test_four_index_executor_compatibility.py -q
```

P4-3A3 is implemented but uncertified. P4-3A4 owns replay/regression certification.
