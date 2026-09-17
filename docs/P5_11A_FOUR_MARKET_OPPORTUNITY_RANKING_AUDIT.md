# P5-11A Four-Market Opportunity Ranking Audit

## 1. Scope and current certified baseline

P5-11 is a proposed pure comparison layer for NIFTY/NSE, BANKNIFTY/NSE,
FINNIFTY/NSE, and SENSEX/BSE. P5-10 is complete (user supplied full-suite
baseline: 12,415 passed, 2 warnings). No canonical four-market opportunity
ranking contract or evaluator currently exists.

## 2. Existing TradeOpportunityV1 contract

`services/contracts/trade_opportunity_v1.py:TradeOpportunityV1` is frozen and
slots-based. Constructor fields are opportunity/snapshot/decision/technical/
option-chain/ranking/session IDs; `created_at`; market identity; expiry;
action/directional bias/option type; option-contract identity/pricing; five
unit scores (`technical_strength`, `option_chain_strength`,
`contract_ranking_score`, `decision_confidence`, `opportunity_score`);
`opportunity_status`; evidence tuples; and JSON-safe metadata. Status values
are READY, READY_WITH_WARNINGS, NO_ACTION, BLOCKED, INSUFFICIENT_DATA,
CONFLICTING, FAILED; actions are BUY/SELL/WAIT/HOLD; bias is BULLISH/BEARISH/
NEUTRAL/MIXED/UNAVAILABLE; option type is CALL/PUT. It restricts identity to
the supported markets, has `opportunity_ready`, serializes with `to_dict`,
`to_json`, `semantic_dict`, and is class-level PAPER-only with live false.

Producer: `services/trade_opportunity/integration.py:build_canonical_trade_opportunity`.
Tests: `tests/test_trade_opportunity_v1.py`,
`tests/test_trade_opportunity_integration.py`, and
`tests/test_four_index_trade_opportunity.py`. This is a constructed,
decision/selected-option-coupled opportunity, not a neutral market candidate.
P5-11 should leave it unchanged and only reference a supplied instance.

## 3. Existing scoring and confidence systems

| Module/API | Behavior | P5-11 classification |
|---|---|---|
| `services/trade_opportunity/integration.py:build_canonical_trade_opportunity` | Clamped weighted technical, option-chain, contract-ranking, and decision confidence; gates status. Clock/UUID-capable defaults. | Compatibility input; unsafe direct ranking. |
| `services/contracts/trade_opportunity_policy_v1.py` | Opportunity builder weights/minima. | Compatibility input. |
| `services/option_contract_ranking/evaluator.py`, `ranker.py:rank_option_contracts` | Deterministic within-underlying option-contract ranking using liquidity/OI/volume/spread/IV/alignment. | Canonical upstream input only. |
| `services/contracts/option_contract_ranking_policy_v1.py` | Per-contract liquidity/spread weights and limits. | Canonical upstream policy only. |
| `services/scoring/market_score_engine.py:calculate_market_score`, `trade_score_engine.py`, `services/technical.py:technical_score` | Mapping/legacy score paths. | Legacy or unsafe for direct ranking. |
| P5-8/P5-9/P5-10 typed results | Deterministic aggregate state/strength/confidence. | Canonical input, consumed once by owner. |

## 4. Existing ranking and best-market logic

`services/option_contract_ranking/ranker.py:rank_option_contracts` ranks
contracts for one underlying, not four markets. Its tests include
`tests/test_option_contract_ranking_ranker.py`, evaluator/pipeline/policy/result
tests, and `tests/test_four_index_option_contract_ranking.py`.
`services/trading_orchestrator.py` calls legacy `best_market`; it is
orchestration/decision-adjacent and remains legacy. No current typed comparator
preserves rejected markets. Unsafe patterns to exclude are max(raw score),
silent omission, provider/order-dependent ties, NIFTY fallback, mutable lists,
and selection that creates BUY/SELL decisions.

## 5. Canonical versus legacy ownership matrix

| Field/dimension | Future treatment |
|---|---|
| `underlying_symbol`, `exchange` | REQUIRED canonical identity. |
| `CanonicalMarketRegimeResultV1`, session | REQUIRED; P5-10 owns regime/suitability and session restriction. |
| Technical, option-chain, contract ranking, P5-8, P5-9, quality | OPTIONAL typed references; upstream owners remain authoritative. |
| `TradeOpportunityV1` | OPTIONAL reference, never reconstructed. |
| Eligibility, rank score, ranks/rejection reasons | DERIVED only by P5-11. |
| Raw provider data, indicators, contracts/strikes/stops/targets/execution | FORBIDDEN. |

## 6. Proposed MarketOpportunityCandidateV1

Propose immutable `MarketOpportunityCandidateV1` with candidate ID,
evaluated-at, identity, canonical regime, session validation, eligibility,
blockers/warnings/source timestamps/metadata and PAPER fields required.
Optional references: TradeOpportunityV1, typed technical/option-chain/contract
ranking, broader-market, external-context, and quality results. Opportunity,
regime, technical, liquidity and quality dimensions are derived only from those
references. It must not own raw inputs, indicator recomputation, sizing,
execution authorization, strikes, stops or targets.

## 7. Candidate eligibility model

Proposed states and precedence: BLOCKED, UNAVAILABLE, CONFLICTING,
ELIGIBLE_WITH_WARNINGS, ELIGIBLE. BLOCKED (regime/entry blocked, analysis
disallowed, hard liquidity/quality failure), UNAVAILABLE (no required usable
evidence), and CONFLICTING cannot win. Warning candidates rank below eligible
candidates. Regime BLOCKED/UNAVAILABLE/CONFLICTING maps directly. Session-owned
restriction, missing opportunity/option evidence, stale data, spread/slippage,
event risk and quality need explicit P5-11C policy gates; no slot disappears.

## 8. Ranking score ownership and no-double-counting rules

Future score is pure, finite `[0,1]`, policy-normalized and clamped. Possible
sources: supplied opportunity confidence, regime suitability, technical and
option confirmation, liquidity quality, quality/freshness. Do not count
technical confidence through both TradeOpportunityV1 and technical result unless
P5-11C defines non-overlap; do not count P5-8/P5-9 directly if represented by
regime; never score event risk directionally or session positively; never use
missing evidence as zero-neutral. Upstream penalties, liquidity, spread and
slippage are consumed once. Warning/conflict/missing/event/spread/slippage/
stale penalty defaults remain P5-11C decisions.

## 9. Proposed FourMarketRankingPolicyV1

`FourMarketRankingPolicyV1` and its default should separately define the exact
four identities; eligibility gates; score weights; one-time penalties;
quality/freshness; liquidity/spread/slippage thresholds; event restrictions;
tie tolerance/order; and all-blocked/all-unavailable/no-eligible behavior.
Defaults are unresolved and must not be inferred from per-contract policies.

## 10. Deterministic tie-breaking

Recommended sequence: eligibility class, final score, opportunity confidence,
regime suitability/confidence, data quality, liquidity quality, fewer warnings,
fewer contradictions, lower spread/slippage, then fixed order NIFTY/NSE,
BANKNIFTY/NSE, FINNIFTY/NSE, SENSEX/BSE. This explicit fallback is suitable;
input list, dict order, hashes, object IDs and provider order are forbidden.
Expose `tie_state` and `tied_markets`.

## 11. Proposed FourMarketOpportunityRankingResultV1

Required immutable fields: ranking ID, evaluated-at, ordered four candidates,
rank/score/eligibility mappings, selected market/candidate (both None if none
eligible), blocked/conflicting/unavailable/warning market tuples, tie state,
tied markets, selection confidence, evidence/contradictions/blockers/warnings,
source timestamps, metadata/schema and PAPER fields. Candidate references may
serialize canonically. No option selection, stops, targets or authorization.

## 12. Four-market completeness and identity rules

Require exactly one slot for each supported identity; reject duplicate,
unsupported or cross-exchange slots. Prefer explicit upstream UNAVAILABLE
candidates rather than accepting a missing slot: every market then remains
visible and gets a deterministic reason. Evaluate each slot exactly once.

## 13. TradeOpportunity regression boundary

Regression files: `tests/test_trade_opportunity_v1.py`,
`tests/test_trade_opportunity_integration.py`,
`tests/test_four_index_trade_opportunity.py`, and relevant
`tests/test_option_contract_ranking_*.py` plus decision/strategy compatibility
tests. P5-11 must not alter TradeOpportunityV1.

## 14. Isolation and architecture boundary

Future ranking imports only standard library and lightweight canonical
contracts/modules. Exclude pandas/numpy/scipy/requests/yfinance/SmartApi/
streamlit, provider/broker/execution/dashboard/news/NLP/AI/runtime modules,
clock/UUID/random calls, network and filesystem writes.

## 15. Proposed files and test plan

| Stage | Files/responsibility | Tests |
|---|---|---|
| P5-11B | `services/contracts/market_opportunity_candidate_v1.py` | candidate/isolation |
| P5-11C | `four_market_ranking_policy_v1.py` | policy/four-market/isolation |
| P5-11D | `four_market_opportunity_ranking_result_v1.py` | result/serialization |
| P5-11E/F/G | `services/opportunity_ranking/eligibility.py`, `scoring.py`, `tie_breaking.py` | eligibility, no-double-counting, ties |
| P5-11H | `aggregate.py`, `service.py`, `__init__.py` | integration/isolation |
| P5-11I/J | fixtures/replay and certification | replay/regression/full suite |

## 16. Risks, incompatibilities, and unresolved decisions

TradeOpportunityV1 is decision and selected-contract coupled and its builder
has clock/UUID-capable defaults; only supplied immutable opportunities are safe
references. P5-11C must decide score dimension overlap, liquidity/spread/
slippage gates, quality contract identity, missing-slot materialization,
all-ineligible semantics, and penalty defaults.

## 17. Locked P5-11 roadmap

P5-11A audit and design; P5-11B MarketOpportunityCandidateV1; P5-11C
FourMarketRankingPolicyV1; P5-11D FourMarketOpportunityRankingResultV1;
P5-11E candidate eligibility evaluator; P5-11F pure candidate scoring;
P5-11G deterministic tie-breaking; P5-11H four-market ranking integration;
P5-11I ranking replay matrix; P5-11J certification. P5-12 must not begin
until P5-11J is green.

## P5-11B MarketOpportunityCandidateV1 implementation

`services/contracts/market_opportunity_candidate_v1.py` adds a frozen,
PAPER-only candidate contract for NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and
SENSEX/BSE. Canonical market regime and session validation are required exact
typed references; TradeOpportunityV1, broader-market intelligence, and external
context remain optional exact typed references. The contract carries supplied
normalized scores, explicit availability flags, candidate status
(READY/READY_WITH_WARNINGS/CONFLICTING/BLOCKED/UNAVAILABLE), and controlled
entry-restriction/data-quality/freshness states.

It enforces status and availability coherence, immutable source timestamps and
deeply immutable JSON-safe metadata, deterministic serialization, and
`live_execution_eligible=False`. Coverage is in
`tests/test_market_opportunity_candidate_v1.py`,
`tests/test_p5_11b_four_market_candidate.py`, and
`tests/test_p5_11b_candidate_isolation.py`. TradeOpportunityV1 remains
unchanged; P5-11C policy remains pending. Test counts are not claimed here.

## P5-11C FourMarketRankingPolicyV1 implementation

`services/contracts/four_market_ranking_policy_v1.py` exports
`FourMarketRankingPolicyV1` and `DEFAULT_FOUR_MARKET_RANKING_POLICY`. It fixes
the four canonical identities, eligibility precedence/flags, normalized
thresholds, nine scalar ranking weights with immutable derived
`ranking_weights`, one-time aggregate penalties, missing-evidence behavior,
normalized liquidity/spread/slippage limits, deterministic tie order and tie
states, all-ineligible preservation, freshness limits, PAPER-only restrictions,
and deterministic serialization. It stores configuration only: no scoring,
eligibility, ranking, or runtime behavior. Tests are
`tests/test_four_market_ranking_policy_v1.py`,
`tests/test_p5_11c_four_market_ranking_policy.py`, and
`tests/test_p5_11c_ranking_policy_isolation.py`. P5-11D remains pending.

## P5-11D FourMarketOpportunityRankingResultV1 implementation

`services/contracts/four_market_opportunity_ranking_result_v1.py` exports the
frozen four-candidate result contract. It enforces canonical candidate
completeness, preserves a supplied ordered candidate view, selected
market/candidate coherence, per-market rank/score/eligibility mappings,
rejection and warning groups, tie states, selection confidence, PAPER-only
restrictions, and deterministic serialization. No ranking calculation occurs.
Tests are `tests/test_four_market_opportunity_ranking_result_v1.py`,
`tests/test_p5_11d_four_market_ranking_result.py`, and
`tests/test_p5_11d_ranking_result_isolation.py`. P5-11E remains pending.

## P5-11E candidate eligibility evaluator

`services/opportunity_ranking/eligibility.py:evaluate_candidate_eligibility`
returns the frozen local `CandidateEligibilityEvaluationV1`. It applies policy
precedence BLOCKED, UNAVAILABLE, CONFLICTING, ELIGIBLE_WITH_WARNINGS, ELIGIBLE
to supplied candidate thresholds, availability, status, restrictions and
freshness state. It records deterministic reasons and missing optional evidence
without calculating a ranking score. Direct normalized spread/slippage fields
do not exist on the candidate contract, so both breach flags remain false and
their direct evaluation is deferred. Tests are
`tests/test_p5_11e_candidate_eligibility.py`,
`tests/test_p5_11e_four_market_eligibility.py`, and
`tests/test_p5_11e_candidate_eligibility_isolation.py`. P5-11F remains pending.

## P5-11F pure candidate scoring

`services/opportunity_ranking/scoring.py:score_market_opportunity_candidate`
returns a frozen `CandidateRankingScoreV1` for one supplied candidate and its
P5-11E eligibility result. It uses exactly the nine canonical normalized
dimensions: opportunity confidence, regime suitability, technical and
option-chain confirmation, broader-market and external-context confirmation,
data quality, liquidity, and execution quality. The usable denominator includes
the four required dimensions and conditionally includes optional dimensions;
when optional evidence exclusion is enabled, unavailable dimensions are removed
from both numerator and denominator rather than treated as neutral zero.

Rankability remains solely owned by P5-11E. Scoring normalizes the weighted
base score, records immutable per-dimension contributions, and returns a zero
final score for non-rankable candidates. Warning, conflict, missing optional
evidence, stale data, event risk, spread, and slippage penalties are applied at
most once in canonical order. It does not re-read child evidence or
TradeOpportunityV1, does not treat session state as positive evidence, and
keeps event risk penalty-only. Direct spread/slippage source fields remain
deferred, so only the supplied P5-11E breach flags can activate those penalties.

Diagnostics and JSON-safe serialization are deterministic. Coverage is in
`tests/test_p5_11f_candidate_scoring.py`,
`tests/test_p5_11f_four_market_scoring.py`, and
`tests/test_p5_11f_candidate_scoring_isolation.py`. P5-11G tie-breaking remains
pending.

## P5-11G deterministic tie-breaking

`services/opportunity_ranking/tie_breaking.py:resolve_candidate_order` returns
the frozen `CandidateTieBreakingResultV1` for one to four already-evaluated
canonical markets. It filters only P5-11E-rankable eligible candidates (and
policy-permitted conflicting candidates), then uses the policy's exact order:
eligibility, final score, opportunity confidence, regime suitability, data
quality, liquidity, execution quality, fewer warnings, fewer contradictions,
deferred spread/slippage, and canonical market order. Numeric criteria honor
the policy tie tolerance; available liquidity and execution quality rank ahead
of unavailable values.

Spread and slippage remain equal/deferred because no canonical candidate fields
exist. Canonical NIFTY, BANKNIFTY, FINNIFTY, SENSEX ordering resolves only
otherwise meaningful ties, records `TIE_RESOLVED`, and is independent of caller
input order. The evaluator preserves original candidate objects and produces
deterministic comparison traces and JSON-safe serialization. It does no scoring,
eligibility evaluation, trade/option selection, or integration. Tests are
`tests/test_p5_11g_tie_breaking.py`,
`tests/test_p5_11g_four_market_tie_breaking.py`, and
`tests/test_p5_11g_tie_breaking_isolation.py`. P5-11H remains pending.

## P5-11H four-market ranking integration

`services/opportunity_ranking/aggregate.py:rank_four_market_opportunities`
and `services/opportunity_ranking/service.py:evaluate_four_market_opportunity_ranking`
provide isolated four-market ranking APIs. The aggregate requires exactly the
four configured canonical markets, normalizes their evaluation order, evaluates
eligibility once and scoring once per candidate, invokes tie-breaking once, and
constructs one `FourMarketOpportunityRankingResultV1`. The service facade only
validates its exact inputs and delegates once, unchanged.

Result provenance is deterministic: all supplied candidate timestamps must
match, and the result ID is derived from canonical candidate IDs. It constructs
canonical eligibility, score, rank, group, source-timestamp, and metadata
mappings. All-ineligible inputs preserve all four candidates and rejection
groups while selecting no fallback market and reporting zero selection
confidence; otherwise selection confidence is the selected final score. No
providers, runtime behavior, trade selection, or score recalculation is added.
Tests are `tests/test_p5_11h_four_market_ranking_integration.py`,
`tests/test_p5_11h_four_market_ranking_call_counts.py`, and
`tests/test_p5_11h_four_market_ranking_isolation.py`. P5-11I and P5-11J remain
pending.

### Policy-permitted conflicting ranking compatibility

`FourMarketOpportunityRankingResultV1` is policy-neutral and structural:
CONFLICTING eligibility may be ranked or unranked when its ordered-candidate,
rank, score, and selection fields are coherent. BLOCKED and UNAVAILABLE remain
non-rankable. `conflicting_markets` remains visible even for a ranked market,
and a conflicting selection is valid only when structurally rank 1. P5-11I
replay design exposed and motivated this correction; P5-11I remains pending
after the repair.

## P5-11I deterministic ranking replay matrix

P5-11I adds `tests/test_p5_11i_ranking_replay_matrix.py`,
`tests/test_p5_11i_ranking_replay_permutations.py`, and
`tests/test_p5_11i_ranking_replay_regressions.py`. The matrix covers the 25
fixed ranking, rejection, threshold, penalty, availability, and tie scenarios;
the required representative cases execute all 24 input permutations. It checks
deterministic aggregate/service equivalence, ranked and unranked conflicting
behavior, fail-closed rejection boundaries, fixed canonical ties, public-result
serialization, no hidden clock/UUID/random/provider behavior, and the
PAPER-only boundary. No production code is changed. P5-11J certification
remains pending.

## P5-11J certification

P5-11J is a certification plan only. Exact user-supplied pytest output is
authoritative; P5-11 is not certified until every group below is green and the
tracking check confirms that no expected P5-11 file remains untracked.

### Group 1 — complete P5-11 focused boundary

```powershell
venv\Scripts\python.exe -m pytest `
tests/test_market_opportunity_candidate_v1.py `
tests/test_p5_11b_four_market_candidate.py `
tests/test_p5_11b_candidate_isolation.py `
tests/test_four_market_ranking_policy_v1.py `
tests/test_p5_11c_four_market_ranking_policy.py `
tests/test_p5_11c_ranking_policy_isolation.py `
tests/test_four_market_opportunity_ranking_result_v1.py `
tests/test_p5_11d_four_market_ranking_result.py `
tests/test_p5_11d_ranking_result_isolation.py `
tests/test_p5_11e_candidate_eligibility.py `
tests/test_p5_11e_four_market_eligibility.py `
tests/test_p5_11e_candidate_eligibility_isolation.py `
tests/test_p5_11f_candidate_scoring.py `
tests/test_p5_11f_four_market_scoring.py `
tests/test_p5_11f_candidate_scoring_isolation.py `
tests/test_p5_11g_tie_breaking.py `
tests/test_p5_11g_four_market_tie_breaking.py `
tests/test_p5_11g_tie_breaking_isolation.py `
tests/test_p5_11h_four_market_ranking_integration.py `
tests/test_p5_11h_four_market_ranking_call_counts.py `
tests/test_p5_11h_four_market_ranking_isolation.py `
tests/test_p5_11i_ranking_replay_matrix.py `
tests/test_p5_11i_ranking_replay_permutations.py `
tests/test_p5_11i_ranking_replay_regressions.py `
-q
```

Focused count/time: **PENDING USER EXECUTION**. Warnings: **PENDING USER
EXECUTION**.

### Group 2 — TradeOpportunity and option-ranking regression

The PowerShell-expanded option-ranking inventory is:
`test_option_contract_ranking_evaluator.py`,
`test_option_contract_ranking_pipeline.py`,
`test_option_contract_ranking_policy_v1.py`,
`test_option_contract_ranking_ranker.py`, and
`test_option_contract_ranking_result_v1.py`.

```powershell
venv\Scripts\python.exe -m pytest `
tests/test_trade_opportunity_v1.py `
tests/test_trade_opportunity_integration.py `
tests/test_four_index_trade_opportunity.py `
tests/test_option_contract_ranking_evaluator.py `
tests/test_option_contract_ranking_pipeline.py `
tests/test_option_contract_ranking_policy_v1.py `
tests/test_option_contract_ranking_ranker.py `
tests/test_option_contract_ranking_result_v1.py `
-q
```

TradeOpportunity/option-ranking count/time: **PENDING USER EXECUTION**.

### Group 3 — recovered P5-8/P5-9/P5-10 regression boundary

The P5-10 audit records the certified 387-test P5-8/P5-9 boundary but not its
literal invocation. The recovered repository command deliberately lets
PowerShell expand the exact P5-prefixed test inventory before pytest starts:

```powershell
venv\Scripts\python.exe -m pytest tests\test_p5_8*.py tests\test_p5_9*.py tests\test_p5_10*.py -q
```

P5-8/P5-9/P5-10 count/time: **PENDING USER EXECUTION**.

### Group 4 — full repository suite

```powershell
venv\Scripts\python.exe -m pytest -q
```

Full-suite count/time: **PENDING USER EXECUTION**. Warnings: **PENDING USER
EXECUTION**.

### Tracking and staging gate

Run these commands after all four groups are green and before committing:

```powershell
git status --short
git add -A
git status --short
git diff --cached --stat
```

Expected staged production files are
`services/contracts/market_opportunity_candidate_v1.py`,
`services/contracts/four_market_ranking_policy_v1.py`,
`services/contracts/four_market_opportunity_ranking_result_v1.py`,
`services/contracts/__init__.py`, and all of
`services/opportunity_ranking/` (`__init__.py`, `eligibility.py`, `scoring.py`,
`tie_breaking.py`, `aggregate.py`, `service.py`). Expected documentation is
this audit. Expected tests are every P5-11B through P5-11I file listed in Group
1. Commit hash/message: **PENDING USER EXECUTION**.

P5-12 may begin only after all groups are green, the expected files are staged,
and the user supplies the exact certification output.
