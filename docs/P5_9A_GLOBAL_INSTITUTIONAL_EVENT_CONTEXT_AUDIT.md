# P5-9A global, institutional, and structured-event context audit

## 1. Executive summary

P5-8 is a strong provider-neutral baseline, but there is no canonical subsystem for global markets, institutional flows, or scheduled event risk. Recommend five contracts: a generic external observation, institutional-flow snapshot, scheduled event, external-context policy, and aggregate external-context result. Defer intermediate result contracts until their evaluators prove a stable public need.

## 2. Current certified position

P5-8 is certified with 11,659 tests passing. Primary identities remain NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE. This document is design-only.

## 3. Repository findings

| Area | Classification | Finding |
|---|---|---|
| Identity, provenance, freshness | Canonical/reusable | Core identity registry plus P5-2 contracts provide normalization, aware time, source health, stale/future, and deterministic serialization. |
| P5-8 intelligence | Canonical/reusable | Broader-market context consumes supplied structured evidence only. |
| Session/holidays | Canonical/reusable | Market-session validation and injected NSE/BSE calendars own regular, holiday, and special-session validity. |
| VIX/FII-DII in MarketSnapshot | Reusable with adaptation | Optional mapping-shaped data/status exists; it is not a pure typed external-context input. |
| Market data yfinance path | Provider-coupled/unsafe | Arbitrary-symbol legacy quote/history path lacks canonical identity, provenance, and freshness. |
| Legacy VIX/FII-DII/master strength | Incomplete/reference | Mapping heuristics cannot be promoted without typed snapshots and policy. |
| News/sentiment/AI summaries | Legacy/unsafe | Narrative and AI interpretation are excluded from deterministic structured context. |
| Expiry discovery | Reusable with adaptation | Existing option expiry data can feed structured expiry context; rollover remains missing. |
| Global indices, futures, DXY, commodities, yields | Missing/unclear | No canonical source, contract, or evaluator found. |
| RBI/CPI/WPI/GDP/Budget/election calendar | Missing | No structured scheduled-event contract/source found. |

## 4. Reusable canonical components

Reuse market identity normalization, P5-2 provenance/freshness vocabulary, frozen slots contracts, finite/bounded values, source IDs/times, tuple reason normalization, semantic serialization, paper-only flags, AuditEventV1, and MarketSessionValidationV1. P5-8 is a later additive consumer, never a provider of external facts.

## 5. Legacy, duplicate, simulated, random, and unsafe components

The yfinance compatibility path is provider-coupled and arbitrary-symbol. Legacy FII/DII, VIX, confidence, market-strength, news/sentiment, and AI summary paths are reference only: they lack a typed freshness/provenance boundary and may generate narrative interpretation. Archive broker/research code is legacy. No canonical random global-context engine was verified; synthetic values must remain explicit test fixtures.

## 6. Data availability matrix

| Input group | Existing evidence | Readiness | Future owner |
|---|---|---|---|
| GIFT/SGX Nifty | No canonical code | Missing | Provider adapter + observation |
| S&P 500, Nasdaq, Dow | yfinance-compatible arbitrary quote path | Provider-coupled/freshness unclear | Adapter + observation |
| US futures, Nikkei, Hang Seng, Shanghai | No verified structured source | Missing | Adapter + observation |
| DXY, Brent, WTI, US/India 10Y | No canonical source | Missing | Adapter + observation |
| India VIX | P5-8 normalized snapshot/context | Canonical boundary; source unverified | P5-8 adapter boundary |
| FII/DII cash | Optional MarketSnapshot mapping/status | Adaptation only | Institutional snapshot |
| FII futures/options positioning | No typed source | Missing | Institutional adapter |
| RBI/CPI/WPI/GDP/Budget/election | No event contract | Missing | Event adapter |
| NSE/BSE holidays/special sessions | Injected session calendars | Reusable | Market-session owner |
| Weekly/monthly expiry | Option contract expiry input | Adaptation | Scheduled-event input |
| Rollover | No canonical context | Missing | Event/market-regime input |

## 7. Gap analysis

Missing: controlled external names/types, source delay, typed institutional currency/unit/provisional fields, scheduled event timing/severity, external policy, pure evaluators, aggregate semantics, and replay. Do not duplicate market-session calendar ownership or use unrestricted news/NLP.

## 8. Recommended minimal canonical architecture

services/contracts:
- external_market_observation_v1.py
- institutional_flow_snapshot_v1.py
- scheduled_market_event_v1.py
- external_context_policy_v1.py
- external_market_context_result_v1.py

services/external_market_context:
- global.py, institutional.py, event_risk.py, evaluator.py, integration.py

One generic observation covers indices, futures, commodities, FX, and yields. Institutional flows require their own unit/date/provisional model. Events require their own timing/severity model. Separate global/institutional/event result contracts should be deferred.

## 9. Detailed contract designs

### ExternalMarketObservationV1 — required

Purpose: one normalized structured fact, not a recommendation. Fields: observation ID, created time, controlled type/name/region/asset class, source ID/time, status, optional current/previous/change/change-percent, direction, delayed flag/delay seconds, blockers/warnings, immutable metadata, paper flags. Initial names: GIFT_NIFTY, SP500, NASDAQ, DOW_JONES, NIKKEI_225, HANG_SENG, SHANGHAI_COMPOSITE, DXY, BRENT_CRUDE, WTI_CRUDE, US_10Y_YIELD, INDIA_10Y_YIELD. Types: INDEX_CLOSE, INDEX_FUTURE, COMMODITY, FX_INDEX, BOND_YIELD, PREMARKET_INDICATOR. Values finite; missing is None; status distinguishes READY, warnings, stale, delayed, unavailable, blocked. Aware source time and deterministic semantic serialization are mandatory.

### InstitutionalFlowSnapshotV1 — required

Purpose: normalized dated FII/DII cash and optional derivative positioning. Fields: snapshot ID, created time, trading date, source ID/time, currency, unit, flow status, provisional, optional FII/DII cash, optional FII index-futures/options net fields, blockers/warnings/metadata, paper flags. Values are finite signed amounts; zero differs from None. Status distinguishes final, provisional, stale, unavailable, blocked. It records facts only.

### ScheduledMarketEventV1 — required

Purpose: confirmed structured scheduled fact, not news analysis. Fields: event ID, created time, name/category, scheduled start/end, affected canonical markets, severity/status, source ID/time, confirmed flag, blockers/warnings/metadata, paper flags. Categories: RBI_POLICY, CPI, WPI, GDP, UNION_BUDGET, ELECTION, EXCHANGE_HOLIDAY, SPECIAL_SESSION, EXPIRY, ROLLOVER, OTHER_SCHEDULED_MACRO. Holiday/special-session truth remains market-session owned.

### ExternalContextPolicyV1 — required

Frozen rules for required observations, per-name max age/delay, group weights, minimum availability, direction/conflict tolerance, mandatory freshness, flow materiality/unit/provisional behavior, event lead/cool-down/severity/block categories, future tolerance/skew, aggregate penalties, and PAPER restriction. Providers supply facts; policy supplies no provider values.

### ExternalMarketContextResultV1 — required

Aggregate for one canonical Indian identity: result ID/time/identity/policy, observation tuple, optional flow snapshot, active/upcoming events, status, bias/strength/risk level, analysis/new-entry restriction, source timestamps, supporting evidence/blockers/contradictions/warnings, paper flags. Bias is BULLISH, BEARISH, NEUTRAL, CONFLICTING, UNAVAILABLE; strength is [0,1]; never BUY/SELL.

## 10. Policy design

Policy owns age/delay, regional/asset weights, minimum availability, direction/conflict tolerance, FII/DII materiality/unit/provisional handling, event lead/cool-down/severity/restriction behavior, skew/future tolerance, and aggregation penalties. Adapters own mapped names, values, source time, delay, and confirmed events. Market-session owns holiday/special session; P5-10 regime, P5-11 ranking, and P8 portfolio retain their existing ownership.

## 11. Global-market safeguards

Previous close and live futures are distinct types. Require session reference, timezone, source time, and delay. Do not combine stale closes and futures without policy. Cap GIFT/NIFTY-futures overlap and group US indices to avoid triple counting. DXY, crude, and yields are modifiers only. Observations describe alignment, never causation.

## 12. Institutional-flow safeguards

Publication can be prior-day/provisional/delayed. Cash and derivatives remain separate. Normalize declared currency/unit before evaluation. FII/DII disagreement is a contradiction, not automatic direction. One day of flow cannot generate a trade decision.

## 13. Structured event-risk safeguards

Only confirmed, timestamped scheduled facts qualify. Policy lead/cool-down windows and deterministic overlap precedence apply. Holidays and special sessions remain session facts. Expiry/rollover are context, not automatic blocks. No unscheduled breaking-news NLP or sentiment engine.

## 14. Ownership and integration boundaries

P5-9 consumes core identity, P5-2 quality, and market-session evidence. Later it informs P5-8/P5-10/P5-11 context only. TradeOpportunityV1 needs a separate additive integration audit. P8 owns portfolio exposure. Dashboard/observability consume outputs only. P5-9 must not own news, final decisions, option selection, plans, sizing, execution, or broker calls.

## 15. Proposed implementation file list

The five contract files and pure package files above; lazy exports; separate adapters outside contracts/domain code; focused public contract docs as needed.

## 16. Proposed test file list

- Contract tests for all five contracts: identity/time/provenance/finite/unavailable/immutability/serialization/execution.
- global context tests: alignment, delay, stale/missing, duplicate/grouping/no double count.
- institutional flow tests: FII/DII, zero versus missing, units, provisional, conflict.
- event-risk tests: RBI/CPI/Budget/election/holiday/special/expiry/rollover windows and overlap.
- aggregate/four-index/isolation/replay tests: precedence, conflicts, no decision, forbidden imports, deterministic fixtures.

## 17. Compatibility risks

Primary risks: stale overnight data treated as live; duplicated US/GIFT exposure; FII/DII unit ambiguity; duplicated calendar ownership; provider symbols leaking into contracts; invented event/news facts; and external context changing current decisions. Controlled vocabulary, source time, policy grouping, injected calendars, and additive integration mitigate them.

## 18. Explicit non-goals

No provider/scraping/news NLP, final BUY/SELL, option selection, plan/sizing, capital reservation, portfolio enforcement, paper/live orders, broker calls, or dashboard behavior.

## 19. Open questions

1. Which licensed source supplies each global observation with source time and delay?
2. What FII/DII unit/currency/publication timetable and derivative positioning source is authoritative?
3. Which calendar source covers RBI, releases, budget, elections, special sessions, expiry, and rollover?
4. Which observations are mandatory per Indian index/session?
5. How should weekend/holiday and delayed-futures overlap be weighted?
6. Should P5-10 or P5-11 first consume external context?

## 20. Ordered P5-9 plan

1. P5-9B external observation and aggregate-result contracts.
2. P5-9C institutional-flow snapshot.
3. P5-9D scheduled-event contract.
4. P5-9E external-context policy.
5. P5-9F global evaluator.
6. P5-9G institutional evaluator.
7. P5-9H event-risk evaluator.
8. P5-9I aggregate evaluator.
9. P5-9J isolated integration.
10. P5-9K four-index replay/isolation.
11. P5-9L compatibility and certification.

## P5-9B implementation status

P5-9B added services/contracts/external_market_observation_v1.py with the
approved twelve-name structured observation universe. It validates controlled
name/type/region/asset combinations, source timestamps, numeric change
consistency, delayed/stale/unavailable states, and ordered affected Indian
market identities. Tests are test_external_market_observation_v1.py,
test_p5_9b_external_observation_matrix.py, and
test_p5_9b_external_observation_isolation.py. Providers and evaluators remain
deferred.

## P5-9C implementation status

P5-9C added services/contracts/institutional_flow_snapshot_v1.py. It separates
cash_flow_unit from derivatives_position_unit, preserves None versus genuine
zero, records publication/session/delay state, and accepts ordered canonical
market applicability without deriving bias. Tests are
test_institutional_flow_snapshot_v1.py,
test_p5_9c_institutional_flow_matrix.py, and
test_p5_9c_institutional_flow_isolation.py. Authoritative flow sources,
event contracts, policy, and evaluators remain deferred.

## P5-9D implementation status

P5-9D added `services/contracts/scheduled_market_event_v1.py`, an immutable,
provider-agnostic record for one normalized scheduled event. Its controlled
categories are RBI policy, CPI, WPI, GDP, Union Budget, election, exchange
holiday, special session, weekly/monthly expiry, rollover, and other scheduled
macro. It records aware normalized timing, confirmation/status/severity,
canonical four-index and NSE/BSE applicability, explicit analysis/new-entry
facts, and a constrained session-override fact. Holiday and special-session
calendar truth, exchange-open determination, expiry calculation, and final
session validation remain owned by the existing market-session/calendar paths.

Tentative and postponed events require warnings; blocked events require
blockers; unavailable confirmation cannot claim active/upcoming certainty; and
analysis denial cannot coexist with permitted new entries. The focused tests
are `test_scheduled_market_event_v1.py`,
`test_p5_9d_scheduled_event_matrix.py`, and
`test_p5_9d_scheduled_event_isolation.py`. Event providers, event windows,
policy (P5-9E), evaluators, aggregate context, and runtime integration remain
deferred.

## P5-9E implementation status

P5-9E added `services/contracts/external_context_policy_v1.py` with
`ExternalContextPolicyV1` and `DEFAULT_EXTERNAL_CONTEXT_POLICY`. The immutable
paper-only policy defines optional per-identity global observations, source-age
and delay limits, controlled observation weights, institutional-flow handling,
event lead/cooldown and severity rules, and aggregate component weights. The
default has no mandatory global observation or component while authoritative
providers are unavailable; missing/stale optional evidence warns, delayed
optional evidence is permitted with a penalty, and all weights use an exact
sum-to-one normalization rule.

Institutional flow is optional by default, permits provisional and previous
session data with warning/penalty rules, and retains declared-unit thresholds
without conversion. Confirmed active HIGH/EXTREME RBI, Budget, CPI, WPI, and
GDP categories are eligible for future entry blocking; analysis remains
allowed during that block. Holidays and special sessions remain owned by
market-session validation, while expiry and rollover remain context only.
Tests are `test_external_context_policy_v1.py`, `test_p5_9e_default_policy.py`,
`test_p5_9e_four_index_policy.py`, and `test_p5_9e_policy_isolation.py`.
Providers/adapters, evaluators, aggregate results, and runtime integration
remain deferred.

## P5-9F implementation status

P5-9F added `services/contracts/global_market_context_result_v1.py` and the
pure `services/external_context/global.py` evaluator exposed as
`evaluate_global_market_context`. It consumes only supplied
`ExternalMarketObservationV1` facts and `ExternalContextPolicyV1`, validates
identity applicability and source freshness against caller-supplied time, and
returns a paper-only immutable result for one canonical Indian identity.

Required evidence can block under policy; optional missing, stale, unavailable,
or permitted delayed evidence produces deterministic warnings. Directional
weight is the configured observation weight times a linear change-percent
magnitude factor, with delayed evidence penalized once. US-equity, crude, and
Asian correlated groups are capped at their largest configured member weight
and preserve mixed evidence as contradictions. Status precedence is BLOCKED,
CONFLICTING, UNAVAILABLE, READY_WITH_WARNINGS, then READY. The evaluator makes
no causal claim and produces no trade or execution action.

Tests are `test_global_market_context_result_v1.py`,
`test_global_market_context_evaluator.py`,
`test_p5_9f_four_index_global_context.py`,
`test_p5_9f_correlated_group_caps.py`, and
`test_p5_9f_global_context_isolation.py`. Institutional/event evaluators,
aggregate context, providers, and runtime integration remain deferred.

## P5-9G implementation status

P5-9G added `services/contracts/institutional_flow_context_result_v1.py` and
the pure `evaluate_institutional_flow_context` evaluator in
`services/external_context/institutional.py`. It consumes supplied typed flow
snapshots only, preserves FII/DII cash and futures/options components
separately, applies only declared-unit thresholds, and never converts or nets
cash against derivatives. RUPEES and MIXED_NORMALIZED values use sign-only,
warning-bearing context.

Missing mandatory, blocked, stale, or disallowed provisional evidence blocks
under policy; optional missing evidence is unavailable context. Conflicts are
preserved for FII/DII, futures/options, and cash versus derivatives. The
outer institutional aggregate weight remains deferred to P5-9I. Tests are
`test_institutional_flow_context_result_v1.py`,
`test_institutional_flow_context_evaluator.py`,
`test_p5_9g_four_index_institutional_context.py`,
`test_p5_9g_institutional_unit_separation.py`, and
`test_p5_9g_institutional_context_isolation.py`. Event evaluation, aggregate
context, providers, and runtime integration remain deferred.

## P5-9H implementation status

P5-9H added `services/contracts/event_risk_context_result_v1.py` and the
pure `evaluate_event_risk_context` evaluator in
`services/external_context/events.py`. It consumes supplied normalized events
at caller-supplied time, applies policy lead/active/cooldown windows once per
event, and preserves deterministic evidence, warnings, blockers, and source
timestamps. Macro blocks require category, severity, confirmation, and window
qualification; expiry/rollover remain context-only by default.

Holiday and special-session events are reported as `SESSION_OWNED` when the
policy assigns final enforcement to market-session validation. This evaluator
does not calculate exchange-open state or execution authorization. Aggregate
context, providers/calendar adapters, and runtime integration remain deferred.

## P5-9I implementation status

P5-9I added `services/contracts/external_market_context_result_v1.py` and the
pure `evaluate_external_market_context` evaluator in
`services/external_context/aggregate.py`. It accepts only already-evaluated
global, institutional, and event context results for one canonical identity;
it never calls sub-evaluators or consumes raw provider facts. Global and
institutional direction are weighted once using the policy aggregate weights;
event context supplies risk and restriction precedence only.

Missing optional components remain explicit warnings rather than neutral
evidence. Required failures and event blocks can fail closed, global versus
institutional disagreement is preserved as conflict, and `SESSION_OWNED`
restrictions remain distinct from an aggregate event-policy block. Providers,
runtime composition, integration, replay, and certification remain deferred.

## P5-9J implementation status

P5-9J added `services/external_context/integration.py` with
`evaluate_external_context_pipeline`. The isolated orchestration validates
typed inputs before any call, then invokes global, institutional, event, and
aggregate evaluators exactly once in that order. It forwards the same canonical
identity, policy object, timestamps, IDs, and exact child result objects;
missing inputs remain child-evaluator semantics. It has no providers, retries,
exception suppression, runtime integration, or decision behavior.

## P5-9K implementation status

P5-9K added fixed-UTC P5-9 replay fixtures in
`tests/fixtures/external_context.py` plus deterministic four-market,
conflict, event-precedence, unavailable-evidence, and isolation replay tests.
Fixtures contain no clock, UUID, random, provider, broker, or network input.
They exercise the pipeline only through typed normalized facts and preserve the
subsystem's provider-free, execution-free boundary. Certification remains
deferred to P5-9L.
