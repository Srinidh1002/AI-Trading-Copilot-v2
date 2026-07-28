# P4-3A four-index identity audit

## Scope and conclusion

Static audit only. The certified canonical identity set is currently exactly
NIFTY/NSE and SENSEX/BSE. BANKNIFTY/NSE and FINNIFTY/NSE are already mentioned
by some legacy market-data code, but are rejected by the certified contracts.
No runtime or tests changed and no tests ran.

## Exact runtime restrictions requiring modification

| Area | Files and symbols | Restriction |
| --- | --- | --- |
| Shared session identity | `services/market_session/identity.py`: `normalize_market_identity`; `policies.py`: `NSE_NIFTY_POLICY`, `BSE_SENSEX_POLICY`; `validator.py`: policy fallback; `__init__.py` exports | Alias map and exchange mapping are NIFTY/SENSEX-only; NSE fallback currently implies NIFTY policy. |
| Option contracts | `services/contracts/option_contract_v1.py`, `option_contract_universe_v1.py`, `selected_option_contract_v1.py` | Inline NIFTY/NSE and SENSEX/BSE pair sets. |
| Trade/risk contracts | `services/contracts/trade_plan_v1.py`, `position_size_result_v1.py` (`_IDENTITIES`), `canonical_risk_result_v1.py` (indirect identity consistency) | Plan and sizing admit only two pairs. |
| P4 contracts | `paper_execution_request_v1.py` (`_MARKETS`), `paper_execution_authorization_v1.py` (`_MARKETS`), `paper_execution_result_v1.py` (`_MARKETS`), `paper_order_state_v1.py` (direction identity), `paper_authorization_result_v1.py` | P4 request/authorization/result identity remains two-market bounded. |
| Sizing/runtime gates | `services/risk/position_sizing.py`: supported-underlying gate; `services/risk/pipeline.py` | Runtime sizing will block new identities even after contract acceptance. |
| Option pipeline | `services/options/selection.py`, `pipeline.py`, `trade_plan.py`; `services/option_contract_selector.py` | Consume contract identity and require review for assumptions/defaults, strike selection, expiry routing, and lot propagation. |
| Market identity/routing | `services/market_identity_guard.py`, `services/underlying_registry.py`, `services/market/instrument_registry.py`, `services/broker/instrument_registry.py`, `services/live_market_configuration.py`, `services/trading_runtime_config.py` | Symbol/exchange configuration and instrument routing require four-index coverage review. |
| Legacy direct maps | `services/market_indices.py`, `services/market_overview.py`, `services/analysis/option_chain.py`, `services/nse_option_chain.py`, `services/live_option_chain_builder.py` | BANKNIFTY is present in some quote maps; FINNIFTY is not consistently present. These are not canonical authority. |

## Contract files affected

Direct pair-set changes are required in: `option_contract_v1.py`,
`option_contract_universe_v1.py`, `selected_option_contract_v1.py`,
`trade_plan_v1.py`, `position_size_result_v1.py`,
`paper_execution_request_v1.py`, `paper_execution_authorization_v1.py`, and
`paper_execution_result_v1.py`. `paper_order_state_v1.py`,
`paper_authorization_result_v1.py`, `canonical_risk_result_v1.py`, and session
contracts require compatibility review because they preserve or compare these
identities even where they do not own the pair set.

## Test coverage affected

At minimum update/add parameterized four-market coverage in:
`test_option_contract_v1.py`, `test_option_contract_universe_v1.py`,
`test_selected_option_contract_v1.py`, `test_trade_plan_v1.py`,
`test_position_size_result_v1.py`, `test_position_sizing.py`,
`test_risk_validation_pipeline.py`, `test_replay_risk_sizing_scenarios.py`,
`test_option_contract_selection.py`, `test_replay_option_trade_plan_scenarios.py`,
`test_canonical_trade_plan_integration.py`, `test_paper_risk_integration.py`,
`test_paper_execution_request_v1.py`, `test_paper_execution_authorization_v1.py`,
`test_paper_execution_result_v1.py`, `test_paper_authorization_validator.py`,
`test_deterministic_paper_executor.py`, and session/configuration/routing tests
including `test_market_identity_validation.py`, `test_market_session_configuration.py`,
`test_nifty_session_validation.py`, and `test_sensex_session_validation.py`.
New BANKNIFTY/FINNIFTY session, expiry, replay, and regression fixtures are
required; existing two-market negative tests must stop treating those identities
as invalid.

## Reusable helpers and duplicate sets

`services/market_session/identity.py` is the closest reusable canonical helper,
but it is currently two-market and session-specific. `services/underlying_registry.py`
and instrument registries are useful routing/data sources but not a single
contract-level authority. At least eight contract modules and the sizing runtime
duplicate literal pair sets; they must not each be independently expanded.

## Lot size, selection, expiry, and sessions

Lot size is contract input (`OptionContractV1`, selection, plan, sizing,
candidate, P4 request/authorization), not a canonical static table. Current
fixtures use synthetic static values; runtime instrument registries/provider
data may derive values. The future registry should own allowed identity and
exchange only; it must not silently invent lot sizes. Contract-provided/current
instrument lot size remains authoritative.

BANKNIFTY and FINNIFTY are NSE identities, so session policy cannot continue to
choose a generic `NSE_NIFTY_POLICY` solely from exchange. Review holiday/special
session and alias handling, then add explicitly named NSE policies or an
identity-aware policy lookup. Option selection must accept the new universe,
preserve exact underlying/exchange/expiry/lot identity, and avoid assuming NIFTY
strikes or NSE defaults. Expiry discovery must be provider/instrument-derived;
P4 must not hard-code expiry calendars.

## Paper and execution implications

Paper candidate, risk, P4 request, authorization, validation result, executor,
result, and order state must all compare the same shared identity. P4 expansion
must be after P3 contract/runtime compatibility so an execution request cannot
accept an identity that sizing or trade planning blocks. Existing BUY/CALL/LONG
and SELL/PUT/LONG mappings remain unchanged for all four markets.

## Compatibility risks and hidden assumptions

Highest risk: changing only contract sets while session fallback and sizing
runtime remain two-market creates inconsistent acceptance/blocking. Additional
risks: tests currently use BANKNIFTY as an invalid-value sentinel; static lot
size fixtures may be mistaken for provider truth; legacy quote maps can expose
an identity that canonical contracts reject; SENSEX/BSE-specific routing must
not be generalized to all non-NSE paths.

## Recommended bounded sequence

1. **P4-3A1 — shared identity registry.** Create one canonical immutable
   four-pair helper, aliases, and identity-aware session-policy routing; no
   contract behavior change until focused tests exist.
2. **P4-3A2 — P3 contracts and runtime compatibility.** Migrate option,
   selection, plan, sizing, risk, session and canonical adapters to that helper;
   add four-market contract/replay/session coverage; preserve NIFTY/SENSEX
   serialization and behavior.
3. **P4-3A3 — P4 compatibility.** Migrate candidate, request, authorization,
   validator, executor, result/state comparisons and tests after P3 accepts all
   four markets; keep execution/manual/live boundaries unchanged.
4. **P4-3A4 — replay, regression, certification.** Add deterministic
   BANKNIFTY/FINNIFTY fixtures, stale/expiry/session negatives, exact lot-size
   propagation checks, focused/full regression, and manual certification.

No broker, provider, lot-size fetching, live execution, short options, or
execution-routing change is part of this audit.
