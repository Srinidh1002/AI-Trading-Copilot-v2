# P6A Trade-plan audit

## Executive summary

**Verified fact:** P5 supplies a deterministic, PAPER-only selected-market
opportunity but deliberately does not create entry, stop, targets, sizing, or
execution requests (`services/trade_opportunity/integration.py:build_canonical_trade_opportunity`).
The repository already contains typed single-target plan, option-selection, and
position-sizing components. It does not contain a canonical deterministic
three-target planning contract. P6 should extend the typed planning boundary,
not reuse legacy mapping engines or execution pipelines.

## Repository areas inspected

Read-only inspection covered `services/contracts`, `services/trade_opportunity`,
`services/opportunity_ranking`, `services/option_contract_ranking`,
`services/options`, `services/risk`, `services/paper`, legacy trade/risk/decision
modules, dashboard/AI paths, paper-trading paths, and related tests including
`test_trade_plan_*`, `test_position_sizing.py`, `test_option_contract_*`, and
`test_p5_12*`.

## Existing strategy and planning components

| Finding | Classification | P6 reuse |
| --- | --- | --- |
| `services/opportunity_ranking/aggregate.py:rank_four_market_opportunities` | P5 public selected-market ranking | Direct P6B input boundary; it remains plan-free. |
| `services/trade_opportunity/integration.py:build_canonical_trade_opportunity` | Typed opportunity with contract identity, reference premium, lot size, blockers/warnings | Direct evidence/input source; its default UUID factory requires injected deterministic IDs in replay. |
| `services/options/trade_plan.py:build_trade_plan` and `TradePlanV1` | Typed single-target legacy planning | Adapt concepts/validation only; cannot represent three targets. |
| `services/options/pipeline.py:create_canonical_trade_plan` | Existing plan assembly | Do not couple P6 directly until its clock/UUID and one-target limitations are isolated. |
| `services/trade_plan_engine.py:build_trade_plan`, `services/decision/trade_engine.py:analyze_trade` | Mapping-based legacy builders | Replace; mapping outputs and legacy dependencies are not P6 canonical inputs. |

## Stop-loss audit

**Verified fact:** `services/trade_level_engine.py:calculate_trade_levels` uses
ATR distance plus support for bullish and resistance for bearish underlying
invalidation. It calculates option-premium stop as a configurable percentage
of premium, validates positive inputs, rounds to two decimals, and places no
orders. It returns a dictionary, has one option target, and does not establish
the P6 policy.

`services/risk_management_engine.py:calculate_trade_levels` returns three
underlying targets and an ATR/support-resistance stop in a dictionary. Its BUY/
SELL/HOLD vocabulary, hard-coded 1.5/2/3/5 ATR multipliers, score, and implicit
defaults conflict with a typed policy and must not be adopted directly.

`services/risk/position_sizing.py:calculate_position_size` validates long
premium geometry (`stop < entry < target`) and derives monetary risk. It is
deterministic only when its clock and ID factory are injected; defaults use
`uuid4`. It is useful for P6I after a three-target plan chooses which target is
the sizing reward basis.

## Target-calculation audit

`risk_management_engine.calculate_trade_levels` is the only confirmed existing
three-target calculation: BUY uses +2/+3/+5 ATR and SELL uses -2/-3/-5 ATR.
It computes RR from target 2 only and has no partial-booking allocation.
`trade_level_engine.calculate_trade_levels` and `TradePlanV1` support exactly
one target. **Gap:** no typed target-1/2/3 ordering, per-target RR, allocation,
or target-specific invalidation rule exists; P6G must own these.

## Entry-zone audit

Existing engines generally use one immediate entry: spot/current price or
`TradeOpportunityV1.reference_option_price`. `trade_level_engine` returns one
`option_entry_price`; `TradePlanV1` has `entry_reference_price`; neither is a
lower/upper entry zone, no-chase limit, or trigger band. P5 session, event,
freshness, and candidate restriction states are reusable blockers, but P6E must
define entry-zone units and tolerances.

## Option-contract selection audit

`services/option_contract_ranking/ranker.py:rank_option_contracts`,
`evaluator.py:evaluate_option_contract`, and `ranking_pipeline.py:build_canonical_option_contract_ranking`
provide typed contract ranking. Reusable types include
`OptionContractV1`, `OptionContractCandidateV1`,
`OptionContractRankingResultV1`, and `SelectedOptionContractV1`; they preserve
strike, expiry, option type, lot size, premium/quote evidence and deterministic
selection/rejection. P5 `TradeOpportunityV1` already carries selected contract
identity, strike, expiry, lot size, and reference option price. P6H must define
when ranking is reused versus revalidated for entry price, liquidity/spread,
expiry, and affordability. No audited selector places orders.

## Capital and quantity audit

`services/risk/position_sizing.py:calculate_position_size` is the strongest
reuse candidate: it floors lots by capital, risk, maximum quantity, and policy
maximum; computes `quantity = approved_lots * lot_size`, capital required,
maximum loss, reward amount, and RR; and returns `PositionSizeResultV1` with
`execution_eligible=False`. It has explicit insufficient-capital and limit
states. `RiskPolicyV1` supplies capital/risk constraints. **Gap:** its only
target is scalar, and it does not model brokerage, taxes, spread cost, or
target allocation. Portfolio sharing is P8 scope and must not be imported.

## Paper-trade and execution boundary audit

`TradePlanV1`, `CanonicalTradePlanResultV1`, `PositionSizeResultV1`, and
`PaperTradeCandidateV1` are typed PAPER-oriented artifacts. The latter has
`stop_loss` and tuple `targets`, but belongs to the paper execution lifecycle.
`PaperExecutionRequestV1`, `services/paper/execution_pipeline.py`,
`services/paper/executor.py`, `services/decision/trade_executor.py`, and broker/
paper-trading orchestrators are prohibited P6D/P6J dependencies: they represent
requests, fills, state, UUID defaults, lifecycle mutation, or execution.

## Legacy trade-plan structures

Legacy dictionary paths (`services/risk_management_engine.py`,
`services/trade_level_engine.py`, `services/trade_plan_engine.py`,
`services/ai_engine.py`, and dashboard/trade modules) expose familiar fields
such as ENTRY, STOP_LOSS, TARGET1--3, signal, and confidence. They are useful
only as formula and compatibility evidence: they are untyped, often depend on
raw mappings, and some are UI/AI/database or execution adjacent. Do not revive
them as P6 APIs.

## Session, event, expiry, and restriction audit

Reusable typed evidence: `MarketSessionValidationV1`, `EventRiskContextResultV1`,
`ExternalMarketContextResultV1`, `CanonicalMarketRegimeResultV1`,
`MarketOpportunityCandidateV1`, P5 eligibility/score results, and
`TradeOpportunityV1` blockers/warnings. They distinguish closed/special
sessions, event blockers/warnings, freshness, conflicts, unavailable evidence,
contract ranking, expiry, and PAPER eligibility. P6B should carry typed
references and immutable propagated reasons, not reinterpret event calendars.

## Contract and unit consistency

P6 contracts must explicitly distinguish underlying index points from option
premium currency, stop/target price from distance, quantity from lots, INR
capital/risk from premium, percentage fractions from percentage points, and
per-target RR from scalar sizing RR. Use aware timestamps, canonical identity,
expiry date, lot size, and currency/price-source fields. Existing code mixes
underlying and premium levels in mappings; this is a material ambiguity.

## Nondeterminism and unsafe logic

`trade_opportunity.integration`, `options.trade_plan`, `risk.position_sizing`,
and paper execution paths expose default `uuid4` factories; deterministic P6
replay must inject IDs/clocks or derive stable IDs. Provider, broker, UI, AI,
database, order, and network paths are prohibited. Legacy mapping engines use
hard-coded ATR multipliers/defaults and must be behind a deterministic adapter
only if later validated. P5 fixtures are test-only and must not become runtime
inputs.

## Existing test coverage

Useful tests include `tests/test_trade_plan_v1.py`, `test_trade_plan_builder.py`,
`test_trade_plan_engine.py`, `test_trade_plan_engine_integrity.py`,
`test_position_sizing.py`, `test_position_size_result_v1.py`,
`test_risk_policy_v1.py`, `test_option_contract_candidate_v1.py`,
`test_option_contract_ranking_{evaluator,pipeline,policy_v1,ranker,result_v1}.py`,
`test_selected_option_contract_v1.py`, `test_trade_opportunity_v1.py`, and
`test_trade_opportunity_integration.py`. Missing are canonical entry zones,
three typed targets, target allocation, per-target RR, deterministic plan IDs,
and P5-selected-market-to-plan replay.

## Reuse matrix

| Capability | Existing module/type | Status | P6 action | Stage | Main gap |
| --- | --- | --- | --- | --- | --- |
| Selected market | `FourMarketOpportunityRankingResultV1` | typed/PAPER | direct | B/J | plan input projection |
| Regime/events/session | P5 typed contexts | typed | direct references | B/C | plan restriction precedence |
| Option selection | option-contract ranking contracts | typed | wrap/adapt | H | entry/liquidity revalidation |
| Entry | `TradePlanV1.entry_reference_price` | scalar | replace evaluator | E | no zone |
| Stop | `trade_level_engine` | mapping | adapt formula only | F | unit/policy conflicts |
| Targets | `risk_management_engine` | mapping, three | adapt formula only | G | no typed RR/allocation |
| Quantity/lots | `PositionSizeResultV1` | typed | adapt | I | scalar target, no charges |
| Brokerage/slippage | scattered execution logic | runtime/legacy | replace | C/I | no canonical model |
| Invalidation | ATR/support/resistance + P5 blockers | mixed | policy + typed result | F/D | no canonical taxonomy |
| Paper representation | `TradePlanV1`/paper contracts | typed | do not execute | D/J | planning/execution separation |
| Serialization | existing frozen v1 contracts | typed | follow conventions | D | multi-target schema |

## Gap analysis by P6 stage

- **P6B:** project selected P5 candidate/opportunity, typed contexts, contract
  ranking, capital input, and aware evaluation time into one canonical input.
- **P6C:** own explicit entry/stop/target/rounding/RR/charges/expiry rules;
  do not inherit legacy constants silently.
- **P6D:** create immutable three-target output with sources, units, blockers,
  warnings, confidence, PAPER fields, and deterministic serialization.
- **P6E/F/G:** implement zone, stop/invalidation, and ordered three-target
  evaluators independently; define long/short/premium geometry and allocation.
- **P6H:** consume ranking public APIs; reject missing, stale, illiquid, or
  unaffordable contracts without execution coupling.
- **P6I:** adapt sizing after defining target basis; add explicit brokerage,
  slippage, spread, lot rounding, and insufficient-capital behavior.
- **P6J:** consume P5 ranking only; return a plan only, never an order/request.
- **P6K:** add deterministic fixtures for bullish/bearish, unavailable,
  conflicts, events/sessions, expiry, affordability, rounding, and hash replay.

## Recommended P6 architecture

Recommendation: small pure components, all PAPER-only: a canonical
`TradePlanInputV1`; `TradePlanningPolicyV1`; `EntryZoneResultV1`;
`StopLossResultV1`; `ThreeTargetResultV1`; an option-selection boundary result;
`CapitalQuantityResultV1`; `ThreeTargetTradePlanResultV1`; and a pure
integration service. Each consumes supplied typed evidence, accepts injected
clock/ID factories where needed, returns immutable blockers/warnings, and has
no provider, broker, database, dashboard, or execution dependency.

## Proposed P6 implementation order

1. P6B canonical input contract
2. P6C policy
3. P6D output contract
4. P6E entry-zone evaluator
5. P6F stop-loss evaluator
6. P6G three-target evaluator
7. P6H option selection boundary
8. P6I capital/quantity
9. P6J integration
10. P6K replay/certification

## P6A conclusion

P6A is complete as an audit only. **Verified:** typed P5 opportunity,
option-ranking, legacy one-target plan, and typed sizing capabilities exist.
**Recommendation:** build a new deterministic three-target planning boundary.
**Unresolved questions:** final stop/target policy, target allocation, charge
model, and whether P6 sizes against target 1, target 2, or a policy-defined
minimum. No production, test, fixture, or P5 file was changed.
