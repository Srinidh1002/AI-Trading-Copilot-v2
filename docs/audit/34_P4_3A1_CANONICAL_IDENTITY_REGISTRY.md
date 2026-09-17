# P4-3A1 canonical identity registry

Created `services.core.market_identity` as the immutable source of truth for
the ordered four-pair set: NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and
SENSEX/BSE. Public functions normalize supported symbols, find expected
exchange, normalize a complete identity, and fail-closed validate a pair.

Aliases preserve existing NIFTY/SENSEX inputs and add common target inputs:
`NIFTY50`, `NIFTY 50`, `BANK NIFTY`, `NIFTY BANK`, `FIN NIFTY`,
`NIFTY FINANCIAL SERVICES`, and `BSE SENSEX`. Unsupported/non-string/empty/
mismatched inputs return `None` or `False`.

`services.market_session.identity.normalize_market_identity` retains its
`MarketIdentity | None` public API and delegates to the shared registry. No
contracts, sizing, selection, paper candidate, authorization, executor, or
session validation policy was expanded in this phase. P4-3A2 owns that work.

The registry initially exposed an import cycle because importing its submodule
executes `services.core.__init__`, which eagerly imported `market_snapshot` and
its options/contracts dependency graph. `services.core.get_market_snapshot` is
now a lazy compatibility wrapper: existing callers retain the same public API,
while importing `services.core.market_identity` does not import market snapshot.

Manual command:
```powershell
venv\Scripts\python.exe -m pytest tests/test_market_identity.py -q
```

P4-3A1 is implemented but uncertified; tests were not run by Codex.
